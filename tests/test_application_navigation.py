import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


try:
    import adios2  # noqa: F401
except ModuleNotFoundError:
    adios2 = types.ModuleType("adios2")
    adios2.FileReader = object
    sys.modules["adios2"] = adios2


from application import SeuratApplication
from controllers import _variable_groups_from_navigation, attach_controllers
from db import CampaignDb
from sqlite_store import SQLiteCampaignCollection


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
    def change(self, *_names):
        def register(callback):
            return callback

        return register


class CampaignDbNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        db_path = Path(self.temp_dir.name) / "campaign.sqlite"
        self.collection = SQLiteCampaignCollection(db_path, "/campaign/example.aca")
        self.addCleanup(self.collection._con.close)

        documents = [
            {
                "campaign_path": "/campaign/example.aca",
                "variable_id": "density",
                "variable_name": "density",
                "variable_type": "variable",
                "source_dataset": "run-a/output.bp",
                "variable_path": "run-a/output.bp/density",
                "producer": "alpha",
                "metadata": {"Shape": "64,64", "AvailableStepsCount": "4"},
            },
            {
                "campaign_path": "/campaign/example.aca",
                "variable_id": "density",
                "variable_name": "density",
                "variable_type": "variable",
                "source_dataset": "run-b/output.bp",
                "variable_path": "run-b/output.bp/density",
                "producer": "beta",
                "metadata": {"Shape": "32,32", "AvailableStepsCount": "3"},
            },
            {
                "campaign_path": "/campaign/example.aca",
                "variable_id": "temperature",
                "variable_name": "temperature",
                "variable_type": "variable",
                "source_dataset": "run-a/scalars.bp",
                "variable_path": "run-a/scalars.bp/temperature",
                "producer": "alpha",
                "metadata": {"Shape": "8", "AvailableStepsCount": "8"},
            },
            {
                "campaign_path": "/campaign/example.aca",
                "variable_id": "step",
                "variable_name": "step",
                "variable_type": "variable",
                "source_dataset": "run-a/scalars.bp",
                "variable_path": "run-a/scalars.bp/step",
                "producer": "alpha",
                "metadata": {"Shape": "1", "AvailableStepsCount": "1"},
            },
            {
                "campaign_path": "/campaign/example.aca",
                "variable_id": "density",
                "variable_name": "density",
                "variable_type": "image",
                "source_dataset": "run-a/output.bp",
                "variable_path": "run-a/images/density.0000.png",
                "producer": "alpha",
                "visualization_name": "heatmap",
                "frame_index": 0,
                "metadata": {"Shape": "480,480"},
            },
        ]
        for document in documents:
            self.collection.insert_one(document)

        self.db = CampaignDb(self.collection)

    def test_existing_grouping_is_stable_and_deduplicates_sources(self):
        self.assertEqual(
            self.db.grouped_variable_names(),
            [
                {
                    "name": "0D",
                    "variables": [
                        {
                            "id": "temperature",
                            "name": "temperature",
                            "label": "temperature",
                            "path": "temperature",
                            "source_dataset": "run-a/scalars.bp",
                        }
                    ],
                },
                {
                    "name": "2D",
                    "variables": [
                        {
                            "id": "density",
                            "name": "density",
                            "label": "density",
                            "path": "density",
                            "source_dataset": "run-a/output.bp",
                        }
                    ],
                },
            ],
        )

    def test_only_visualized_preserves_current_catalog_behavior(self):
        groups = self.db.grouped_variable_names(only_visualized=True)

        self.assertEqual([group["name"] for group in groups], ["2D"])
        self.assertEqual(
            [variable["id"] for variable in groups[0]["variables"]],
            ["density"],
        )

    def test_source_filter_preserves_the_matching_concrete_source(self):
        groups = self.db.grouped_variable_names(
            extra_filter={"source_dataset": "run-b/output.bp"}
        )

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["variables"][0]["id"], "density")
        self.assertEqual(
            groups[0]["variables"][0]["source_dataset"],
            "run-b/output.bp",
        )

    def test_application_projection_round_trips_to_legacy_ui_payload(self):
        expected = self.db.grouped_variable_names()
        application = SeuratApplication(self.db)

        navigation = application.get_navigation(
            {
                "view": "variables",
                "query": {},
                "only_visualized": False,
                "parent_id": None,
            }
        )

        self.assertEqual(_variable_groups_from_navigation(navigation), expected)
        self.assertEqual(navigation[0]["id"], "variable-group:0D")
        self.assertEqual(navigation[0]["children"][0]["id"], "variable:temperature")
        self.assertEqual(navigation[1]["count"], 1)

    def test_application_forwards_catalog_filters(self):
        application = SeuratApplication(self.db)

        navigation = application.get_navigation(
            {
                "view": "variables",
                "query": {"source_dataset": "run-b/output.bp"},
                "only_visualized": False,
            }
        )
        groups = _variable_groups_from_navigation(navigation)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["variables"][0]["id"], "density")
        self.assertEqual(
            groups[0]["variables"][0]["source_dataset"],
            "run-b/output.bp",
        )

    def test_controller_refresh_preserves_variable_groups_state_contract(self):
        state = RecordingState(
            queryFilter={},
            querySourceRestrictionFilter={},
            showOnlyVisualizedVars=False,
            variableGroupCollapsed={},
        )
        server = SimpleNamespace(state=state, controller=RecordingController())
        refresh = attach_controllers(
            server=server,
            db=self.db,
            collection=self.collection,
            parse_campaign=lambda *_args, **_kwargs: None,
            campaign_path="/campaign/example.aca",
        )

        refresh()

        self.assertEqual(state.variableGroups, self.db.grouped_variable_names())
        self.assertEqual(state.variableNames, ["temperature", "density"])
        self.assertEqual(
            state.variableLabelsById,
            {"temperature": "temperature", "density": "density"},
        )
        self.assertEqual(state.variableGroupCollapsed, {"0D": False, "2D": False})
        self.assertTrue(state.dbOk)
        self.assertEqual(state.dbStatus, "Connected")
        self.assertIn("run_query", server.controller.actions)
        self.assertEqual(len(server.controller.on_server_ready.callbacks), 1)

    def test_unimplemented_navigation_views_fail_explicitly(self):
        application = SeuratApplication(self.db)

        for view in ("objects", "campaign"):
            with self.subTest(view=view):
                with self.assertRaisesRegex(ValueError, f"Unsupported navigation view: {view}"):
                    application.get_navigation({"view": view})


if __name__ == "__main__":
    unittest.main()
