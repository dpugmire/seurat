import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.change_callbacks = {}

    def change(self, *_names):
        def register(callback):
            for name in _names:
                self.change_callbacks.setdefault(name, []).append(callback)
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

    def test_scalar_plot_uses_steps_without_explicit_time_values(self):
        class PlotReader:
            def __init__(self):
                self.reads = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, path, **kwargs):
                self.reads.append((path, kwargs))
                return [10.0, 20.0, 30.0]

        reader = PlotReader()
        metadata = {"SingleValue": True, "AvailableStepsCount": "3"}
        with patch("db.FileReader", return_value=reader):
            x, y, x_label = CampaignDb._read_plot_series(
                "/campaign/example.aca",
                "run-a/output.bp/internal_energy",
                metadata,
            )

        self.assertEqual(x.tolist(), [0.0, 1.0, 2.0])
        self.assertEqual(y.tolist(), [10.0, 20.0, 30.0])
        self.assertEqual(x_label, "step")
        self.assertEqual(
            reader.reads,
            [
                (
                    "run-a/output.bp/internal_energy",
                    {"step_selection": [0, 3]},
                )
            ],
        )

    def test_scalar_plot_uses_only_explicit_matching_time_values(self):
        explicit_values, explicit_label = CampaignDb._plot_timeline_values(
            3,
            [0.0, 0.25, 1.0],
        )
        self.assertEqual(explicit_values.tolist(), [0.0, 0.25, 1.0])
        self.assertEqual(explicit_label, "time")
        self.assertEqual(
            CampaignDb._plot_timeline_values(3, [0.0, 1.0])[0].tolist(),
            [0.0, 1.0, 2.0],
        )
        self.assertEqual(
            CampaignDb._plot_timeline_values(3, None)[1],
            "step",
        )

    def test_scalar_plot_candidate_preserves_declared_time_values(self):
        self.collection.insert_one(
            {
                "campaign_path": "/campaign/example.aca",
                "variable_id": "internal_energy",
                "variable_name": "internal_energy",
                "variable_type": "variable",
                "source_dataset": "run-a/output.bp",
                "variable_path": "run-a/output.bp/internal_energy",
                "time_source": "variable:time",
                "time_values": [0.0, 0.25, 1.0],
                "metadata": {"SingleValue": True, "AvailableStepsCount": "3"},
            }
        )

        candidate = self.db.scalar_plot_candidate("internal_energy")

        self.assertEqual(candidate["time_source"], "variable:time")
        self.assertEqual(candidate["time_values"], [0.0, 0.25, 1.0])

    def make_controller(self):
        state = RecordingState()
        init_state(state, self.db)
        state.variableLabelsById = {
            "density": "density",
            "temperature": "temperature",
        }
        server = SimpleNamespace(state=state, controller=RecordingController())
        attach_controllers(
            server=server,
            db=self.db,
            collection=self.collection,
            parse_campaign=lambda *_args, **_kwargs: None,
            campaign_path="/campaign/example.aca",
        )
        return state, server.controller

    def test_controller_registration_contract_is_complete(self):
        state, controller = self.make_controller()

        self.assertEqual(
            set(controller.actions),
            {
                "add_grid_column",
                "add_grid_row",
                "add_var_to_grid",
                "apply_plot_settings",
                "apply_plugin_options",
                "apply_scalar_field_settings",
                "apply_source_dialog",
                "apply_source_dialog_filter",
                "assign_var_to_grid_cell",
                "cancel_plot_settings",
                "cancel_plugin_options",
                "cancel_scalar_field_settings",
                "cancel_scalar_plot_generation",
                "cancel_source_dialog",
                "clear_all_sources",
                "clear_grid_cell",
                "clear_query",
                "clear_source_filter",
                "close_help_modal",
                "confirm_scalar_plot_generation",
                "context_menu_cell_add_source",
                "context_menu_cell_clear",
                "context_menu_cell_pick_visualization",
                "context_menu_cell_plot_settings",
                "context_menu_cell_reset_span",
                "context_menu_cell_reset_view",
                "context_menu_cell_run_source_plugin",
                "context_menu_cell_scalar_field_settings",
                "context_menu_cell_select",
                "context_menu_cell_shrink_height",
                "context_menu_cell_shrink_width",
                "context_menu_cell_sources",
                "context_menu_cell_span_down",
                "context_menu_cell_span_right",
                "context_menu_item_add",
                "context_menu_item_select",
                "delete_grid_column",
                "delete_grid_row",
                "hide_context_menu",
                "move_grid_cell",
                "open_plot_settings_plugin_options",
                "pick_grid_cell_visualization",
                "pick_tile_visualization",
                "pick_var",
                "reset_grid_cell_span",
                "reset_grid_track_sizes",
                "reset_plot_settings",
                "reset_plugin_options",
                "reset_scalar_field_settings",
                "run_query",
                "select_all_sources",
                "select_source",
                "select_var",
                "set_active_grid_cell",
                "set_dragged_var",
                "set_grid_cell_size",
                "set_grid_fit_min_cell_size",
                "set_grid_layout_mode",
                "set_grid_layout_size",
                "set_grid_sizing_mode",
                "show_query_help",
                "show_source_filter_help",
                "shrink_grid_cell_height",
                "shrink_grid_cell_width",
                "sort_sources",
                "source_dialog_select",
                "span_grid_cell_down",
                "span_grid_cell_right",
                "toggle_add_source",
                "toggle_movie_details",
                "toggle_source_visibility",
                "toggle_sources",
                "toggle_timeline_driver_cell",
                "toggle_variable_group",
                "update_plot_background_color",
                "update_plot_cursor_color",
                "update_plot_grid_color",
                "update_plot_series_color",
                "update_plot_series_line_style",
                "update_plugin_option_value",
            },
        )
        self.assertEqual(
            set(controller.triggers),
            {
                "assign_var_to_grid_cell_trigger",
                "hide_context_menu_trigger",
                "move_grid_cell_trigger",
                "set_grid_track_sizes_trigger",
                "set_grid_track_weights_trigger",
                "show_cell_context_menu",
                "show_item_context_menu",
            },
        )
        self.assertEqual(
            set(state.change_callbacks),
            {"selectedVar", "showOnlyVisualizedVars", "variablePaneView"},
        )
        self.assertEqual(len(controller.on_server_ready.callbacks), 1)

    def test_server_ready_lifecycle_reingests_and_refreshes_catalog(self):
        state = RecordingState()
        init_state(state, self.db)
        controller = RecordingController()
        server = SimpleNamespace(state=state, controller=controller)
        parse_calls = []

        def parse_campaign(campaign_path, collection, **kwargs):
            parse_calls.append((campaign_path, kwargs))
            collection.insert_one(
                {
                    "campaign_path": campaign_path,
                    "variable_id": "energy",
                    "variable_name": "energy",
                    "variable_type": "variable",
                    "source_dataset": "run/scalars.bp",
                    "metadata": {"SingleValue": True, "AvailableStepsCount": "3"},
                }
            )

        attach_controllers(
            server=server,
            db=self.db,
            collection=self.collection,
            parse_campaign=parse_campaign,
            campaign_path="/campaign/example.aca",
            image_association_schema_path="/schemas/images.yaml",
            campaign_schema_path="/schemas/campaign.yaml",
        )

        controller.on_server_ready.callbacks[0]()

        self.assertEqual(
            parse_calls,
            [
                (
                    "/campaign/example.aca",
                    {
                        "image_association_schema_path": "/schemas/images.yaml",
                        "campaign_schema_path": "/schemas/campaign.yaml",
                    },
                )
            ],
        )
        self.assertEqual(state.variableNames, ["energy"])
        self.assertIn("variables=1", state.dbStatus)

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

    def test_grid_layout_controller_preserves_cell_geometry(self):
        state, controller = self.make_controller()

        controller.actions["set_grid_layout_size"](2, 4)

        self.assertEqual((state.gridRows, state.gridCols), (2, 4))
        self.assertEqual(len(state.gridCells), 8)
        self.assertEqual(
            [
                (cell["grid_row"], cell["grid_col"])
                for cell in state.gridCells
            ],
            [
                (1, 1),
                (1, 2),
                (1, 3),
                (1, 4),
                (2, 1),
                (2, 2),
                (2, 3),
                (2, 4),
            ],
        )
        self.assertTrue(
            all(
                cell["row_span"] == 1
                and cell["col_span"] == 1
                and not cell["grid_hidden"]
                for cell in state.gridCells
            )
        )

        controller.actions["add_grid_row"]()
        self.assertEqual((state.gridRows, state.gridCols), (3, 4))
        self.assertEqual(len(state.gridCells), 12)

        state.activeGridCell = 1
        controller.actions["delete_grid_column"]()
        self.assertEqual((state.gridRows, state.gridCols), (3, 3))
        self.assertEqual(len(state.gridCells), 9)
        self.assertEqual(state.activeGridCell, -1)

    def test_move_and_clear_cell_reset_timeline_driver_and_selection(self):
        state, controller = self.make_controller()
        state.gridCells[0].update(
            {
                "variable_id": "density",
                "variable_name": "density",
                "status": "ready",
                "frame_count": 3,
                "frame_indices": [0, 1, 2],
                "time_values": [0.0, 0.5, 1.0],
            }
        )

        controller.actions["toggle_timeline_driver_cell"](0)
        self.assertEqual(state.timelineDriverCell, 0)

        controller.actions["move_grid_cell"](0, 4)

        self.assertEqual(state.timelineDriverCell, -1)
        self.assertEqual(state.gridCells[0]["variable_id"], "")
        self.assertEqual(state.gridCells[4]["variable_id"], "density")
        self.assertEqual(state.activeGridCell, 4)
        self.assertEqual(state.selectedGridCellIndices, [4])
        self.assertEqual(state.selectedGridCellMap, {"4": True})

        controller.actions["toggle_timeline_driver_cell"](4)
        self.assertEqual(state.timelineDriverCell, 4)

        controller.actions["clear_grid_cell"](4)
        self.assertEqual(state.timelineDriverCell, -1)
        self.assertEqual(state.gridCells[4]["variable_id"], "")
        self.assertEqual(state.selectedGridCellIndices, [])
        self.assertEqual(state.selectedGridCellMap, {})

    def test_spanning_cell_hides_and_restores_covered_slot(self):
        state, controller = self.make_controller()
        state.gridLayoutMode = "spanning"
        state.gridCells[0].update(
            {
                "variable_id": "density",
                "variable_name": "density",
                "status": "ready",
            }
        )

        controller.actions["span_grid_cell_right"](0)

        self.assertEqual(state.gridCells[0]["col_span"], 2)
        self.assertTrue(state.gridCells[1]["grid_hidden"])
        self.assertEqual(state.activeGridCell, 0)

        controller.actions["shrink_grid_cell_width"](0)

        self.assertEqual(state.gridCells[0]["col_span"], 1)
        self.assertFalse(state.gridCells[1]["grid_hidden"])

    def test_shift_selection_includes_contiguous_selectable_cells(self):
        state, controller = self.make_controller()
        for index in range(5):
            state.gridCells[index].update(
                {
                    "variable_id": "density",
                    "variable_name": "density",
                    "status": "ready",
                }
            )
        state.activeGridCell = 0
        state.selectedGridCellIndices = [0]
        state.selectedGridCellMap = {"0": True}

        controller.actions["set_active_grid_cell"](4, multi=1)

        self.assertEqual(state.activeGridCell, 4)
        self.assertEqual(state.selectedGridCellIndices, [0, 1, 2, 3, 4])
        self.assertEqual(
            state.selectedGridCellMap,
            {str(index): True for index in range(5)},
        )

    def test_unimplemented_navigation_views_fail_explicitly(self):
        application = SeuratApplication(self.db)

        for view in ("objects", "campaign"):
            with self.subTest(view=view):
                with self.assertRaisesRegex(ValueError, f"Unsupported navigation view: {view}"):
                    application.get_navigation({"view": view})


if __name__ == "__main__":
    unittest.main()
