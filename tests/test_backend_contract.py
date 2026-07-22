import unittest
from types import SimpleNamespace

from application import SeuratApplication
from seurat.backends import BackendStatus, LocalCampaignBackend
from seurat.controllers import attach_controllers
from seurat.state import init_state


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

SOURCE_SUMMARY = {
    "variable_id": "energy",
    "num_sources": 0,
    "global_min": 1.0,
    "global_max": 4.0,
    "mean_min": 1.5,
    "mean_max": 3.5,
    "median_min": 1.5,
    "median_max": 3.5,
    "sources": [],
}


class RecordingCampaignDb:
    def __init__(self):
        self.ok = True
        self.last_error = ""
        self.variable_calls = []
        self.file_calls = []
        self.source_summary_calls = []
        self.source_lookup_calls = []
        self.source_restriction_calls = []

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

    def variable_min_max_summary(self, variable_id, **kwargs):
        self.source_summary_calls.append((variable_id, kwargs))
        return {
            "variable": variable_id,
            "num_sources": 1,
            "global_min": "1",
            "global_max": 4,
            "mean_min": 1.5,
            "mean_max": 3.5,
            "median_min": 1.5,
            "median_max": 3.5,
            "sources": [
                {
                    "source_label": "run/output",
                    "variable_id": variable_id,
                    "variable_name": "energy",
                    "variable_type": "variable",
                    "variable_path": "energy",
                    "source_dataset": "run/output.bp",
                    "source_datasets": ["run/output.bp"],
                    "files": ["output.bp"],
                    "producer": "run",
                    "casename": "case-a",
                    "file": "output.bp",
                    "num_timesteps": 34,
                    "min": "1",
                    "max": 4,
                }
            ],
        }

    def source_for_visualization(
        self, variable_id, visualization_name, **kwargs
    ):
        self.source_lookup_calls.append((variable_id, visualization_name, kwargs))
        return {
            "source_label": "run/output",
            "variable_id": variable_id,
            "source_dataset": "run/output.bp",
            "producer": "run",
            "casename": "case-a",
            "file": "output.bp",
            "visualization_name": visualization_name,
        }

    def source_restriction_summary(self, queries):
        self.source_restriction_calls.append(queries)
        return {"filter": {"producer": "run"}, "count": 2}


class FakeCatalogBackend:
    def __init__(
        self,
        navigation=None,
        status=None,
        source_summary=None,
        source=None,
        source_restriction=None,
    ):
        self.navigation = navigation or []
        self.status = status or BackendStatus(ok=True)
        self.source_summary = source_summary or dict(SOURCE_SUMMARY)
        self.source = source
        self.source_restriction = source_restriction or {"query": {}, "count": 0}
        self.requests = []
        self.source_summary_requests = []
        self.source_lookup_requests = []
        self.source_restriction_requests = []

    def get_navigation(self, request):
        self.requests.append(request)
        return self.navigation

    def get_status(self):
        return self.status

    def get_source_summary(self, request):
        self.source_summary_requests.append(request)
        return self.source_summary

    def find_source(self, request):
        self.source_lookup_requests.append(request)
        return self.source

    def resolve_source_restriction(self, request):
        self.source_restriction_requests.append(request)
        return self.source_restriction


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

    def test_source_summary_normalizes_rows_and_assigns_stable_opaque_ids(self):
        db = RecordingCampaignDb()
        backend = LocalCampaignBackend(db)
        request = {"variable_id": "energy", "query": {"producer": "run"}}

        first = backend.get_source_summary(request)
        second = backend.get_source_summary(request)
        other_variable = backend.get_source_summary(
            {"variable_id": "temperature", "query": {"producer": "run"}}
        )

        self.assertEqual(first["variable_id"], "energy")
        self.assertEqual(first["global_min"], 1.0)
        self.assertEqual(first["sources"][0]["minimum"], 1.0)
        self.assertEqual(first["sources"][0]["maximum"], 4.0)
        self.assertEqual(first["sources"][0]["label"], "run/output")
        self.assertEqual(first["sources"][0]["num_timesteps"], 34)
        self.assertTrue(
            first["sources"][0]["id"].startswith("local-source:v1:")
        )
        self.assertEqual(
            first["sources"][0]["id"],
            second["sources"][0]["id"],
        )
        self.assertEqual(
            first["sources"][0]["id"],
            other_variable["sources"][0]["id"],
        )
        self.assertEqual(
            db.source_summary_calls,
            [
                ("energy", {"extra_filter": {"producer": "run"}}),
                ("energy", {"extra_filter": {"producer": "run"}}),
                ("temperature", {"extra_filter": {"producer": "run"}}),
            ],
        )

    def test_source_lookup_uses_the_same_stable_identity(self):
        db = RecordingCampaignDb()
        backend = LocalCampaignBackend(db)

        source = backend.find_source(
            {
                "variable_id": "energy",
                "visualization_name": "timeseries",
                "query": {"producer": "run"},
            }
        )
        summary_source = backend.get_source_summary(
            {"variable_id": "energy", "query": {}}
        )["sources"][0]

        self.assertIsNotNone(source)
        self.assertEqual(source["id"], summary_source["id"])
        self.assertEqual(
            db.source_lookup_calls,
            [
                (
                    "energy",
                    "timeseries",
                    {"extra_filter": {"producer": "run"}},
                )
            ],
        )

    def test_source_restriction_hides_local_result_shape(self):
        db = RecordingCampaignDb()
        backend = LocalCampaignBackend(db)
        queries = [{"producer": "run"}]

        result = backend.resolve_source_restriction({"queries": queries})

        self.assertEqual(result, {"query": {"producer": "run"}, "count": 2})
        self.assertEqual(db.source_restriction_calls, [queries])


class BackendInjectionTests(unittest.TestCase):
    def test_application_delegates_to_explicit_backend(self):
        source = {"id": "remote-source:7", "label": "run/output"}
        backend = FakeCatalogBackend(
            VARIABLE_NAVIGATION,
            BackendStatus(ok=False, error="remote unavailable"),
            source=source,
            source_restriction={"query": {"producer": "run"}, "count": 2},
        )
        application = SeuratApplication(backend=backend)
        request = {"view": "variables", "query": {}, "only_visualized": False}

        self.assertIs(application.get_navigation(request), VARIABLE_NAVIGATION)
        self.assertEqual(backend.requests, [request])
        self.assertEqual(
            application.get_backend_status(),
            BackendStatus(ok=False, error="remote unavailable"),
        )
        source_request = {"variable_id": "energy", "query": {}}
        self.assertEqual(application.get_source_summary(source_request), SOURCE_SUMMARY)
        self.assertEqual(backend.source_summary_requests, [source_request])
        lookup_request = {
            "variable_id": "energy",
            "visualization_name": "timeseries",
            "query": {},
        }
        self.assertIs(application.find_source(lookup_request), source)
        self.assertEqual(backend.source_lookup_requests, [lookup_request])
        restriction_request = {"queries": [{"producer": "run"}]}
        self.assertEqual(
            application.resolve_source_restriction(restriction_request),
            {"query": {"producer": "run"}, "count": 2},
        )
        self.assertEqual(
            backend.source_restriction_requests,
            [restriction_request],
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

    def test_controller_source_panel_uses_injected_backend(self):
        backend = FakeCatalogBackend(source_summary=dict(SOURCE_SUMMARY))
        state = RecordingState()
        db = SimpleNamespace(ok=True, last_error="")
        init_state(state, db)
        state.variableLabelsById = {"energy": "Energy"}
        server = SimpleNamespace(state=state, controller=RecordingController())

        attach_controllers(
            server=server,
            backend=backend,
            db=db,
            collection=SimpleNamespace(),
            parse_campaign=lambda *_args, **_kwargs: None,
            campaign_path="/campaign/example.aca",
        )
        state.change_callbacks["selectedVar"][0]("energy")

        self.assertEqual(
            backend.source_summary_requests,
            [{"variable_id": "energy", "query": {}}],
        )
        self.assertEqual(state.detailsSelectedVarId, "energy")
        self.assertEqual(state.detailsNumSources, 0)
        self.assertEqual(state.detailsGlobalMin, "1")
        self.assertEqual(state.detailsGlobalMax, "4")

    def test_controller_source_restriction_uses_injected_backend(self):
        backend = FakeCatalogBackend(
            source_restriction={"query": {"producer": "run"}, "count": 2}
        )
        state = RecordingState()
        db = SimpleNamespace(ok=True, last_error="")
        init_state(state, db)
        state.queryText = "source(producer == 'run')"
        server = SimpleNamespace(state=state, controller=RecordingController())

        attach_controllers(
            server=server,
            backend=backend,
            db=db,
            collection=SimpleNamespace(),
            parse_campaign=lambda *_args, **_kwargs: None,
            campaign_path="/campaign/example.aca",
        )
        server.controller.actions["run_query"]()

        self.assertEqual(
            backend.source_restriction_requests,
            [{"queries": [{"producer": "run"}]}],
        )
        self.assertEqual(state.querySourceRestrictionFilter, {"producer": "run"})
        self.assertEqual(state.querySourceRestrictionCount, 2)
        self.assertEqual(state.queryStatus, "Query OK · 2 source runs")


if __name__ == "__main__":
    unittest.main()
