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
                "scalar_field_settings": {"colormap": "plasma"},
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

        cell = document["state"]["grid"]["cells"][0]
        self.assertEqual(cell["variable_id"], "density")
        self.assertEqual(cell["source_dataset"], "run/output.bp")
        self.assertEqual(cell["plot_settings"], {"show_grid": False})
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
