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
from state_init import init_state


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

    def test_file_grouping_lists_variables_under_each_source_dataset(self):
        groups = self.db.grouped_variables_by_source_dataset()

        self.assertEqual(
            [group["name"] for group in groups],
            ["run-a/output", "run-a/scalars", "run-b/output"],
        )
        self.assertEqual(
            [[variable["id"] for variable in group["variables"]] for group in groups],
            [["density"], ["temperature"], ["density"]],
        )

    def test_file_grouping_honors_only_visualized(self):
        groups = self.db.grouped_variables_by_source_dataset(only_visualized=True)

        self.assertEqual([group["name"] for group in groups], ["run-a/output"])
        self.assertEqual([variable["id"] for variable in groups[0]["variables"]], ["density"])

    def test_file_grouping_uses_schema_declared_file_per_timestep_group(self):
        for source_dataset in ("xgc.3d.00010.bp", "xgc.3d.00012.bp"):
            self.collection.insert_one(
                {
                    "campaign_path": "/campaign/example.aca",
                    "variable_id": "potential",
                    "variable_name": "potential",
                    "variable_type": "variable",
                    "source_dataset": source_dataset,
                    "producer": "xgc",
                    "schema_file_group": "xgc_3d",
                    "schema_mode": "file_per_timestep",
                    "schema_pattern": "xgc.3d.*.bp",
                    "schema_num_timesteps": 2,
                    "metadata": {"Shape": "64,64"},
                }
            )

        groups = self.db.grouped_variables_by_source_dataset(
            extra_filter={"producer": "xgc"}
        )

        self.assertEqual([group["name"] for group in groups], ["xgc.3d.*"])
        self.assertEqual(groups[0]["file_count"], 2)
        self.assertEqual(
            [variable["id"] for variable in groups[0]["variables"]],
            ["potential"],
        )

        summary = self.db.variable_min_max_summary(
            "potential",
            extra_filter={"producer": "xgc"},
        )
        self.assertEqual(summary["num_sources"], 1)
        self.assertEqual(summary["sources"][0]["source_label"], "xgc.3d.*")

        navigation = SeuratApplication(self.db).get_navigation(
            {
                "view": "files",
                "query": {"producer": "xgc"},
                "only_visualized": False,
            }
        )
        self.assertEqual(navigation[0]["resource"]["file_count"], 2)
        self.assertEqual(
            _variable_groups_from_navigation(navigation)[0]["file_count"],
            2,
        )

    def test_schema_file_counts_use_timestep_metadata(self):
        schema_groups = {
            "xgc_3d": "xgc.3d.*.bp",
            "xgc_f3d": "xgc.f3d.*.bp",
            "xgc_fsourcediag": "xgc.fsourcediag.*.bp",
        }
        for schema_file_group, schema_pattern in schema_groups.items():
            self.collection.insert_one(
                {
                    "campaign_path": "/campaign/example.aca",
                    "variable_id": "potential",
                    "variable_name": "potential",
                    "variable_type": "variable",
                    "source_dataset": schema_file_group,
                    "producer": "schema-count-test",
                    "schema_file_group": schema_file_group,
                    "schema_mode": "file_per_timestep",
                    "schema_pattern": schema_pattern,
                    "schema_num_timesteps": 5,
                    "metadata": {"Shape": "64,64"},
                }
            )

        for step in (10, 12, 14, 16, 18):
            self.collection.insert_one(
                {
                    "campaign_path": "/campaign/example.aca",
                    "variable_id": "potential",
                    "variable_name": "potential",
                    "variable_type": "image",
                    "source_dataset": f"xgc.3d.{step:05d}.bp",
                    "producer": "schema-count-test",
                    "schema_file_group": "xgc_3d",
                    "schema_mode": "file_per_timestep",
                    "schema_pattern": "xgc.3d.*.bp",
                    "schema_num_timesteps": 5,
                    "visualization_name": "heatmap",
                }
            )

        groups = self.db.grouped_variables_by_source_dataset(
            extra_filter={"producer": "schema-count-test"}
        )

        self.assertEqual(
            {group["name"]: group.get("file_count") for group in groups},
            {
                "xgc.3d.*": 5,
                "xgc.f3d.*": 5,
                "xgc.fsourcediag.*": 5,
            },
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

    def test_application_file_navigation_uses_file_nodes(self):
        application = SeuratApplication(self.db)

        navigation = application.get_navigation(
            {
                "view": "files",
                "query": {},
                "only_visualized": False,
            }
        )

        self.assertEqual(
            [node["label"] for node in navigation],
            ["run-a/output", "run-a/scalars", "run-b/output"],
        )
        self.assertTrue(all(node["kind"] == "file" for node in navigation))
        self.assertEqual(navigation[0]["children"][0]["resource"]["variable_id"], "density")
        self.assertEqual(
            navigation[0]["children"][0]["resource"]["source_dataset"],
            "run-a/output.bp",
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
        self.assertEqual(state.variableGroupCollapsed, {"0D": True, "2D": True})
        self.assertTrue(state.dbOk)
        self.assertEqual(state.dbStatus, "Connected")
        self.assertIn("run_query", server.controller.actions)
        self.assertEqual(len(server.controller.on_server_ready.callbacks), 1)

    def test_controller_refresh_supports_file_view(self):
        state = RecordingState(
            queryFilter={},
            querySourceRestrictionFilter={},
            showOnlyVisualizedVars=False,
            variablePaneView="files",
            variableGroupCollapsed={},
            variableGroupCollapsedByView={"variables": {}, "files": {}},
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

        self.assertEqual(
            [group["name"] for group in state.variableGroups],
            ["run-a/output", "run-a/scalars", "run-b/output"],
        )
        self.assertEqual(state.variableNames, ["density", "temperature"])
        self.assertEqual(
            state.variableGroupCollapsedByView["files"],
            {
                "run-a/output": True,
                "run-a/scalars": True,
                "run-b/output": True,
            },
        )

        server.controller.actions["toggle_variable_group"]("run-a/output")
        state.variablePaneView = "variables"
        refresh()
        server.controller.actions["toggle_variable_group"]("0D")

        state.variablePaneView = "files"
        refresh()
        self.assertFalse(state.variableGroupCollapsed["run-a/output"])

        state.variablePaneView = "variables"
        refresh()
        self.assertFalse(state.variableGroupCollapsed["0D"])

    def test_sources_dialog_opens_for_details_when_active_cell_is_empty(self):
        state = RecordingState()
        init_state(state, self.db)
        state.detailsSelectedVar = "density"
        state.detailsSelectedVarId = "density"
        state.selectedVar = "density"
        state.variableLabelsById = {"density": "density"}
        state.sourceRowsAll = [{"_key": "density-source"}]
        state.sourceRows = list(state.sourceRowsAll)
        state.selectedSourceKeys = ["density-source"]
        state.activeGridCell = 0

        server = SimpleNamespace(state=state, controller=RecordingController())
        attach_controllers(
            server=server,
            db=self.db,
            collection=self.collection,
            parse_campaign=lambda *_args, **_kwargs: None,
            campaign_path="/campaign/example.aca",
        )

        server.controller.actions["toggle_sources"]()

        self.assertTrue(state.showSourcesModal)
        self.assertEqual(state.sourceDialogTitle, "Sources: density")
        self.assertEqual(state.sourceDialogCellIndex, -1)
        self.assertEqual(state.sourceDialogTargetCellIndices, [])
        self.assertEqual(state.sourceDialogInitialSelectedSourceKeys, ["density-source"])

        server.controller.actions["apply_source_dialog"]()

        self.assertFalse(state.showSourcesModal)
        self.assertFalse(state.sourceDialogStatusIsError)
        self.assertEqual(state.detailsSelectedVarId, "density")

    def test_explicit_schema_source_without_visualization_does_not_fall_back(self):
        for schema_file_group, schema_pattern in (
            ("xgc_3d", "xgc.3d.*.bp"),
            ("xgc_f3d", "xgc.f3d.*.bp"),
        ):
            self.collection.insert_one(
                {
                    "campaign_path": "/campaign/example.aca",
                    "variable_id": "potential",
                    "variable_name": "potential",
                    "variable_type": "variable",
                    "source_dataset": schema_file_group,
                    "schema_file_group": schema_file_group,
                    "schema_mode": "file_per_timestep",
                    "schema_pattern": schema_pattern,
                    "metadata": {"Shape": "64,64", "Min": "-1", "Max": "1"},
                }
            )

        self.collection.insert_one(
            {
                "campaign_path": "/campaign/example.aca",
                "variable_id": "potential",
                "variable_name": "potential",
                "variable_type": "image",
                "source_dataset": "xgc.3d.00010.bp",
                "schema_file_group": "xgc_3d",
                "schema_mode": "file_per_timestep",
                "schema_pattern": "xgc.3d.*.bp",
                "visualization_name": "heatmap",
                "visualization_kind": "mesh-field",
                "variable_path": "visualizations/potential.png",
                "frame_index": 10,
            }
        )

        state = RecordingState()
        init_state(state, self.db)
        state.variableLabelsById = {"potential": "potential"}
        state.gridCells[0].update(
            {
                "variable_id": "potential",
                "variable_name": "potential",
                "visualization_name": "heatmap",
                "selected_visualization": "heatmap",
                "schema_file_group": "xgc_3d",
                "schema_mode": "file_per_timestep",
                "status": "ready",
            }
        )
        state.activeGridCell = 0

        server = SimpleNamespace(state=state, controller=RecordingController())
        attach_controllers(
            server=server,
            db=self.db,
            collection=self.collection,
            parse_campaign=lambda *_args, **_kwargs: None,
            campaign_path="/campaign/example.aca",
        )

        server.controller.actions["toggle_sources"]()
        f3d_key = next(
            row["_key"]
            for row in state.sourceRows
            if row["schema_file_group"] == "xgc_f3d"
        )
        server.controller.actions["source_dialog_select"](f3d_key)
        server.controller.actions["apply_source_dialog"]()

        cell = state.gridCells[0]
        self.assertEqual(cell["schema_file_group"], "xgc_f3d")
        self.assertEqual(cell["status"], "no-visualizations")
        self.assertEqual(cell["note"], "No visualization for source xgc.f3d.*")
        self.assertFalse(state.showSourcesModal)

    def test_unimplemented_navigation_views_fail_explicitly(self):
        application = SeuratApplication(self.db)

        for view in ("objects", "campaign"):
            with self.subTest(view=view):
                with self.assertRaisesRegex(ValueError, f"Unsupported navigation view: {view}"):
                    application.get_navigation({"view": view})


if __name__ == "__main__":
    unittest.main()
