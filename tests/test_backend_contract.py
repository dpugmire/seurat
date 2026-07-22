import unittest
from types import SimpleNamespace

from application import SeuratApplication
from seurat.backends import BackendStatus, LocalCampaignBackend
from seurat.controllers import attach_controllers


VARIABLE_NAVIGATION = [
    {
        "id": "variable-group:0D",
        "kind": "variable-group",
        "label": "0D",
        "resource": None,
        "children": [
            {
                "id": "variable:energy",
                "kind": "variable",
                "label": "energy",
                "resource": {
                    "variable_id": "energy",
                    "name": "energy",
                    "label": "energy",
                    "path": "energy",
                    "source_dataset": "run/output.bp",
                },
                "children": [],
                "has_children": False,
                "count": None,
            }
        ],
        "has_children": True,
        "count": 1,
    }
]


class RecordingCampaignDb:
    def __init__(self):
        self.ok = True
        self.last_error = ""
        self.variable_calls = []
        self.file_calls = []

    def grouped_variable_names(self, **kwargs):
        self.variable_calls.append(kwargs)
        return [
            {
                "name": "0D",
                "variables": [
                    {
                        "id": "energy",
                        "name": "energy",
                        "label": "energy",
                        "path": "energy",
                        "source_dataset": "run/output.bp",
                    }
                ],
            }
        ]

    def grouped_variables_by_source_dataset(self, **kwargs):
        self.file_calls.append(kwargs)
        return [
            {
                "name": "run/output",
                "source_dataset": "run/output.bp",
                "file_count": 3,
                "variables": [
                    {
                        "id": "energy",
                        "name": "energy",
                        "label": "energy",
                        "path": "energy",
                        "source_dataset": "run/output.bp",
                    }
                ],
            }
        ]


class FakeCatalogBackend:
    def __init__(self, navigation=None, status=None):
        self.navigation = navigation or []
        self.status = status or BackendStatus(ok=True)
        self.requests = []

    def get_navigation(self, request):
        self.requests.append(request)
        return self.navigation

    def get_status(self):
        return self.status


class RecordingEvent:
    def __init__(self):
        self.callbacks = []

    def add(self, callback):
        self.callbacks.append(callback)


class RecordingController:
    def __init__(self):
        self.actions = {}
        self.triggers = {}
        self.on_server_ready = RecordingEvent()

    def add(self, name):
        def register(callback):
            self.actions[name] = callback
            return callback

        return register

    def trigger(self, name):
        def register(callback):
            self.triggers[name] = callback
            return callback

        return register


class RecordingState(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.change_callbacks = {}

    def change(self, *_names):
        def register(callback):
            for name in _names:
                self.change_callbacks.setdefault(name, []).append(callback)
            return callback

        return register


class LocalCampaignBackendTests(unittest.TestCase):
    def test_variable_navigation_normalizes_local_groups(self):
        db = RecordingCampaignDb()
        backend = LocalCampaignBackend(db)

        navigation = backend.get_navigation(
            {
                "view": "variables",
                "query": {"producer": "run"},
                "only_visualized": True,
            }
        )

        self.assertEqual(navigation, VARIABLE_NAVIGATION)
        self.assertEqual(
            db.variable_calls,
            [
                {
                    "extra_filter": {"producer": "run"},
                    "only_visualized": True,
                }
            ],
        )

    def test_file_navigation_preserves_group_metadata(self):
        db = RecordingCampaignDb()
        backend = LocalCampaignBackend(db)

        navigation = backend.get_navigation(
            {"view": "files", "query": {}, "only_visualized": False}
        )

        self.assertEqual(
            db.file_calls,
            [{"extra_filter": None, "only_visualized": False}],
        )
        self.assertEqual(navigation[0]["id"], "file:run/output")
        self.assertEqual(navigation[0]["resource"]["file_count"], 3)
        self.assertEqual(
            navigation[0]["children"][0]["resource"]["source_dataset"],
            "run/output.bp",
        )

    def test_status_hides_campaign_db_implementation(self):
        db = RecordingCampaignDb()
        db.ok = False
        db.last_error = "sidecar unavailable"

        self.assertEqual(
            LocalCampaignBackend(db).get_status(),
            BackendStatus(ok=False, error="sidecar unavailable"),
        )


class BackendInjectionTests(unittest.TestCase):
    def test_application_delegates_to_explicit_backend(self):
        backend = FakeCatalogBackend(
            VARIABLE_NAVIGATION,
            BackendStatus(ok=False, error="remote unavailable"),
        )
        application = SeuratApplication(backend=backend)
        request = {"view": "variables", "query": {}, "only_visualized": False}

        self.assertIs(application.get_navigation(request), VARIABLE_NAVIGATION)
        self.assertEqual(backend.requests, [request])
        self.assertEqual(
            application.get_backend_status(),
            BackendStatus(ok=False, error="remote unavailable"),
        )

    def test_controller_catalog_refresh_uses_injected_backend(self):
        backend = FakeCatalogBackend(VARIABLE_NAVIGATION)
        state = RecordingState(
            queryFilter={},
            querySourceRestrictionFilter={},
            showOnlyVisualizedVars=False,
            variablePaneView="variables",
            variableGroupCollapsed={},
            variableGroupCollapsedByView={"variables": {}, "files": {}},
        )
        server = SimpleNamespace(state=state, controller=RecordingController())
        db = SimpleNamespace(ok=False, last_error="must not drive catalog refresh")

        refresh = attach_controllers(
            server=server,
            backend=backend,
            db=db,
            collection=SimpleNamespace(),
            parse_campaign=lambda *_args, **_kwargs: None,
            campaign_path="/campaign/example.aca",
        )
        refresh()

        self.assertEqual(state.variableNames, ["energy"])
        self.assertEqual(state.variableLabelsById, {"energy": "energy"})
        self.assertTrue(state.dbOk)
        self.assertEqual(state.dbStatus, "Connected")
        self.assertEqual(
            backend.requests,
            [
                {
                    "view": "variables",
                    "query": {},
                    "only_visualized": False,
                    "parent_id": None,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
