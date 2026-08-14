import json
import unittest
from types import SimpleNamespace

from seurat.models.workspace_state import (
    WORKSPACE_FORMAT,
    WORKSPACE_VERSION,
    WorkspaceStateError,
    default_workspace_filename,
    parse_workspace_document,
    validate_workspace_campaign,
    workspace_document,
    workspace_json,
)
from seurat.state import init_state


class WorkspaceStateTests(unittest.TestCase):
    def make_state(self):
        state = SimpleNamespace()
        init_state(state, SimpleNamespace(ok=True, last_error=""))
        state.queryText = "var == 'density'"
        state.activeViewerActionPlan = {
            "version": 1,
            "actions": [
                {
                    "type": "catalog.query",
                    "arguments": {"result_variable_id": "density"},
                }
            ],
        }
        state.activeNaturalLanguageQuery = "show density"
        state.variablePaneView = "files"
        state.showOnlyVisualizedVars = True
        state.gridCells[0].update(
            {
                "variable_id": "density",
                "variable_name": "Density",
                "visualization_name": "heatmap",
                "selected_visualization": "heatmap",
                "_source_key": "source-a",
                "_source_keys": ["source-a"],
                "_source_fields_list": [
                    {
                        "_source_key": "source-a",
                        "source_dataset": "run/output.bp",
                    }
                ],
                "source_dataset": "run/output.bp",
                "plot_settings": {"show_grid": False},
                "scalar_field_settings": {
                    "render_mode": "both",
                    "colormap": "plasma",
                    "contours": {
                        "level_mode": "values",
                        "values": [-1.0, 0.0, 1.0],
                        "color": "#ff0000",
                    },
                },
                "src": "data:image/png;base64,not-persisted",
                "plot": {"series": [{"x": [0], "y": [1]}]},
                "frame_sources": ["not-persisted"],
                "visualization_options": ["heatmap", "contour"],
                "status": "ready",
            }
        )
        state.activeGridCell = 0
        state.selectedGridCellIndices = [0]
        state.selectedGridCellMap = {"0": True}
        return state

    def test_workspace_document_keeps_semantic_state_only(self):
        document = workspace_document(
            self.make_state(),
            "/campaign/example.aca",
        )

        self.assertEqual(document["format"], WORKSPACE_FORMAT)
        self.assertEqual(document["version"], WORKSPACE_VERSION)
        self.assertEqual(document["campaign"], {"name": "example.aca"})
        self.assertEqual(
            document["state"]["catalog"]["query_text"],
            "var == 'density'",
        )
        self.assertEqual(
            document["state"]["catalog"]["viewer_action"]["actions"][0]["type"],
            "catalog.query",
        )
        self.assertEqual(
            document["state"]["catalog"]["viewer_action"]["version"],
            1,
        )
        self.assertEqual(
            document["state"]["catalog"]["natural_language_query"],
            "show density",
        )

        cell = document["state"]["grid"]["cells"][0]
        self.assertEqual(cell["variable_id"], "density")
        self.assertEqual(cell["source_dataset"], "run/output.bp")
        self.assertEqual(cell["plot_settings"], {"show_grid": False})
        self.assertEqual(
            cell["scalar_field_settings"]["contours"]["values"],
            [-1.0, 0.0, 1.0],
        )
        self.assertEqual(
            cell["scalar_field_settings"]["contours"]["color"],
            "#ff0000",
        )
        self.assertNotIn("src", cell)
        self.assertNotIn("plot", cell)
        self.assertNotIn("frame_sources", cell)
        self.assertNotIn("visualization_options", cell)
        self.assertNotIn("status", cell)

    def test_json_round_trip_accepts_utf8_bytes(self):
        content = workspace_json(
            self.make_state(),
            "/campaign/example.aca",
        )
        document = parse_workspace_document(
            b"\xef\xbb\xbf" + content.encode("utf-8")
        )

        self.assertEqual(document, json.loads(content))
        validate_workspace_campaign(document, "/copy/example.aca")

    def test_workspace_layout_round_trip_retains_panes_tabs_and_grids(self):
        state = self.make_state()
        second_grid = dict(state.workspaceLayout["panes"][0]["tabs"][0]["grid"])
        second_grid["cells"] = [dict(cell) for cell in second_grid["cells"]]
        second_grid["cells"][0]["variable_id"] = "temperature"
        state.workspaceLayout = {
            "split_direction": "horizontal",
            "split_ratio": 0.5,
            "active_pane_id": "pane-1",
            "active_tab_id": "tab-1",
            "panes": [
                state.workspaceLayout["panes"][0],
                {
                    "id": "pane-2",
                    "active_tab_id": "tab-2",
                    "tabs": [
                        {
                            "id": "tab-2",
                            "title": "2D Fields",
                            "grid": second_grid,
                        }
                    ],
                },
            ],
        }

        document = parse_workspace_document(
            workspace_json(state, "/campaign/example.aca")
        )
        workspace = document["state"]["workspace"]

        self.assertEqual(workspace["split_direction"], "horizontal")
        self.assertEqual(len(workspace["panes"]), 2)
        self.assertEqual(workspace["panes"][1]["tabs"][0]["title"], "2D Fields")
        self.assertEqual(
            workspace["panes"][1]["tabs"][0]["grid"]["cells"][0][
                "variable_id"
            ],
            "temperature",
        )

    def test_legacy_single_grid_document_without_workspace_is_accepted(self):
        document = workspace_document(
            self.make_state(),
            "/campaign/example.aca",
        )
        del document["state"]["workspace"]

        parsed = parse_workspace_document(json.dumps(document))

        self.assertNotIn("workspace", parsed["state"])

    def test_rejects_wrong_format_version_and_campaign(self):
        document = workspace_document(
            self.make_state(),
            "/campaign/example.aca",
        )
        document["version"] = WORKSPACE_VERSION + 1
        with self.assertRaisesRegex(
            WorkspaceStateError,
            "Unsupported state version",
        ):
            parse_workspace_document(json.dumps(document))

        document["version"] = WORKSPACE_VERSION
        with self.assertRaisesRegex(
            WorkspaceStateError,
            'for campaign "example.aca"',
        ):
            validate_workspace_campaign(document, "/campaign/other.aca")

    def test_rejects_non_json_numbers_and_oversized_grid(self):
        with self.assertRaisesRegex(WorkspaceStateError, "Invalid JSON number"):
            parse_workspace_document(
                '{"format":"seurat-workspace","version":1,'
                '"campaign":{"name":"example.aca"},'
                '"state":{"catalog":{},"grid":{"cells":[NaN]},'
                '"visualization":{}}}'
            )

        document = workspace_document(
            self.make_state(),
            "/campaign/example.aca",
        )
        document["state"]["grid"]["cells"] = [{} for _ in range(65)]
        with self.assertRaisesRegex(WorkspaceStateError, "8x8 grid limit"):
            parse_workspace_document(json.dumps(document))

    def test_default_filename_is_campaign_based_and_safe(self):
        self.assertEqual(
            default_workspace_filename("/campaign/example.aca"),
            "example.json",
        )
        self.assertEqual(
            default_workspace_filename("/campaign/My Campaign!.aca"),
            "My_Campaign.json",
        )


if __name__ == "__main__":
    unittest.main()
