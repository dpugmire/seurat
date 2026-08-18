import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from trame.app import TrameComponent, get_server

import app as compatibility_app
from seurat.app import SeuratApp, build_parser, main
from seurat.backends import LocalCampaignBackend
from seurat import module as seurat_module
from seurat.components import SeuratUI
from seurat.components.query_assistant import QueryAssistantDialog
from seurat.widgets import CanvasRuntime, GridRuntime, InteractionRuntime, ResizeRuntime
from ui import build_ui


class SeuratAppTests(unittest.TestCase):
    def test_composition_root_connects_application_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaign_path = Path(temp_dir) / "sample.aca"
            collection = SimpleNamespace(path=Path(temp_dir) / "sample.sqlite")
            db = SimpleNamespace(ok=True, last_error="")
            controller_calls = []
            ui_calls = []
            refresh_variable_list = object()
            built_ui = object()
            interaction_log = SimpleNamespace(enabled=False)

            def attach(**kwargs):
                controller_calls.append(kwargs)
                return refresh_variable_list

            def build(server, refresh, campaign_name):
                ui_calls.append((server, refresh, campaign_name))
                return built_ui

            server = get_server(
                f"seurat-composition-{id(self)}",
                client_type="vue3",
            )
            app = SeuratApp(
                campaign_path,
                image_association_schema_path="~/images.yaml",
                campaign_schema_path="~/campaign.yaml",
                server=server,
                collection=collection,
                db=db,
                interaction_log=interaction_log,
                controller_attacher=attach,
                ui_builder=build,
            )

        self.assertIs(app.server, server)
        self.assertIs(app.collection, collection)
        self.assertIs(app.db, db)
        self.assertIs(app.interaction_log, interaction_log)
        self.assertIsInstance(app.backend, LocalCampaignBackend)
        self.assertIs(app.refresh_variable_list, refresh_variable_list)
        self.assertIs(app.ui, built_ui)
        self.assertEqual(
            server.state.trame__scripts,
            [
                f"{seurat_module.BASE_URL}/seurat.js",
                f"{seurat_module.BASE_URL}/seurat-media-runtime.js",
                f"{seurat_module.BASE_URL}/seurat-plot-runtime.js",
                f"{seurat_module.BASE_URL}/seurat-timeline-runtime.js",
                f"{seurat_module.BASE_URL}/seurat-grid-runtime.js",
                f"{seurat_module.BASE_URL}/seurat-canvas-layout.js",
                f"{seurat_module.BASE_URL}/seurat-canvas-runtime.js",
                f"{seurat_module.BASE_URL}/seurat-interaction-runtime.js",
                f"{seurat_module.BASE_URL}/seurat-resize-runtime.js",
                f"{seurat_module.BASE_URL}/seurat-history-runtime.js",
            ],
        )
        self.assertEqual(
            server.state.trame__vue_use,
            [
                "seuratGridRuntime",
                "seuratCanvasRuntime",
                "seuratInteractionRuntime",
                "seuratResizeRuntime",
                "seuratHistoryRuntime",
            ],
        )
        self.assertEqual(
            server.state.trame__styles,
            [f"{seurat_module.BASE_URL}/seurat.css"],
        )
        self.assertEqual(
            server.serve[seurat_module.BASE_URL],
            seurat_module.serve[seurat_module.BASE_URL],
        )
        self.assertEqual(app.campaign_path, str(campaign_path))
        self.assertEqual(
            app.image_association_schema_path,
            str(Path("~/images.yaml").expanduser()),
        )
        self.assertEqual(
            app.campaign_schema_path,
            str(Path("~/campaign.yaml").expanduser()),
        )
        self.assertIs(controller_calls[0]["server"], server)
        self.assertIs(controller_calls[0]["backend"], app.backend)
        self.assertIs(controller_calls[0]["db"], db)
        self.assertIs(controller_calls[0]["collection"], collection)
        self.assertIs(controller_calls[0]["interaction_log"], interaction_log)
        self.assertEqual(controller_calls[0]["campaign_path"], str(campaign_path))
        self.assertEqual(
            ui_calls,
            [(server, refresh_variable_list, "sample.aca")],
        )

    def test_top_level_app_preserves_public_entry_points(self):
        self.assertIs(compatibility_app.SeuratApp, SeuratApp)
        self.assertIs(compatibility_app.build_parser, build_parser)

        args = build_parser().parse_args(
            [
                "campaign.aca",
                "--image-association-schema",
                "images.yaml",
                "--campaign-schema",
                "campaign.yaml",
            ]
        )
        self.assertEqual(args.campaign_path, "campaign.aca")
        self.assertEqual(args.image_association_schema, "images.yaml")
        self.assertEqual(args.campaign_schema, "campaign.yaml")
        self.assertFalse(args.demo)

        demo_args = build_parser().parse_args(["--demo"])
        self.assertTrue(demo_args.demo)
        self.assertIsNone(demo_args.campaign_path)

    def test_demo_cli_launches_generated_campaign_and_closes_sidecar(self):
        generated = SimpleNamespace(
            campaign_path=Path("/tmp/seurat-demo/synthetic-demo.aca"),
            sidecar_path=Path("/tmp/seurat-demo/synthetic-demo.sqlite"),
        )

        @contextmanager
        def demo_context():
            yield generated

        collection = MagicMock()
        application = MagicMock()
        with patch("seurat.app.temporary_demo_campaign", side_effect=demo_context), patch(
            "seurat.app.open_sqlite_collection",
            return_value=collection,
        ) as open_collection, patch(
            "seurat.app.SeuratApp",
            return_value=application,
        ) as app_class:
            main(["--demo"])

        open_collection.assert_called_once_with(
            str(generated.campaign_path),
            db_path=str(generated.sidecar_path),
        )
        app_class.assert_called_once_with(
            campaign_path=str(generated.campaign_path),
            collection=collection,
        )
        application.server.start.assert_called_once_with()
        collection.close.assert_called_once_with()

    def test_cli_requires_exactly_one_input_mode(self):
        for argv in ([], ["campaign.aca", "--demo"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                main(argv)

        with self.assertRaises(SystemExit):
            main(["--demo", "--campaign-schema", "schema.yaml"])

    def test_ui_is_composed_from_trame_components(self):
        server = get_server(
            f"seurat-ui-components-{id(self)}",
            client_type="vue3",
        )

        ui = build_ui(server, campaign_name="sample.aca")

        self.assertIsInstance(ui, SeuratUI)
        for component in (
            ui.query_toolbar,
            ui.query_assistant,
            ui.help_dialog,
            ui.workspace_menu,
            ui.variable_panel,
            ui.grid_workspace,
            ui.context_menu,
            ui.grid_workspace.source_dialog,
            ui.grid_workspace.scalar_plot_dialog,
            ui.grid_workspace.plot_settings_panel,
            ui.grid_workspace.plugin_options_panel,
            ui.grid_workspace.scalar_field_settings_panel,
        ):
            self.assertIsInstance(component, TrameComponent)
            self.assertIs(component.server, server)

        self.assertIn("sample.aca", ui.layout.html)
        self.assertNotIn("Campaign loaded:", ui.layout.html)
        self.assertIn("Save As…", ui.layout.html)
        self.assertIn("Current state file", ui.layout.html)
        self.assertIn("New tab", ui.layout.html)
        self.assertNotIn("Pane and tab actions", ui.layout.html)
        self.assertNotIn("seurat-workspace-pane-menu-button", ui.layout.html)
        self.assertIn("Split right", ui.layout.html)
        self.assertIn("Split down", ui.layout.html)
        self.assertIn("seurat-workspace-tab-bar", ui.layout.html)
        self.assertIn("seurat-workspace-tab-dock-preview", ui.layout.html)
        self.assertIn("seurat-workspace-grid-preview", ui.layout.html)
        self.assertNotIn('id="seurat-workspace-state-file"', ui.layout.html)
        self.assertIn('id="seurat-variable-column"', ui.layout.html)
        self.assertIn("Search variables", ui.layout.html)
        self.assertIn("variableSearchText", ui.layout.html)
        self.assertIsInstance(ui.query_assistant, QueryAssistantDialog)
        self.assertIn("Query Assistant", ui.layout.html)
        self.assertIn("Source Filter Assistant", ui.layout.html)
        self.assertIn("Visualization Assistant", ui.layout.html)
        self.assertIn("Natural language + Ask", ui.layout.html)
        self.assertIn("Apply to Source Filter", ui.layout.html)
        self.assertIn("Add to Grid", ui.layout.html)
        self.assertIn("queryAssistantRequestText", ui.layout.html)
        self.assertIn("queryAssistantProposalText", ui.layout.html)
        self.assertIn("queryAssistantProposalSummary", ui.layout.html)
        self.assertIn("Resolved Advanced Query", ui.layout.html)
        self.assertIn("Translate natural language into a query", ui.layout.html)
        self.assertIn("Add a variable to the active grid cell", ui.layout.html)
        self.assertIn('id="seurat-context-menu"', ui.layout.html)
        self.assertIn("scalarFieldSettingsBackground", ui.layout.html)
        self.assertIn("scalarFieldSettingsShowHeatmap", ui.layout.html)
        self.assertIn("scalarFieldSettingsShowContours", ui.layout.html)
        self.assertIn("scalarFieldSettingsContourLevelMode", ui.layout.html)
        self.assertIn("scalarFieldSettingsContourValues", ui.layout.html)
        self.assertIn("scalarFieldSettingsContourCount", ui.layout.html)
        self.assertIn("scalarFieldSettingsContourColor", ui.layout.html)
        self.assertIn('id="seurat-representation-details"', ui.layout.html)
        self.assertIn("detailsSourceRepresentation", ui.layout.html)
        self.assertIn("detailsDerivedRepresentations", ui.layout.html)
        self.assertIsInstance(ui.grid_workspace.runtime, GridRuntime)
        self.assertIn("seurat-grid-runtime", ui.layout.html)
        self.assertIsInstance(ui.interaction_runtime, InteractionRuntime)
        self.assertIsInstance(ui.canvas_runtime, CanvasRuntime)
        self.assertIn("seurat-canvas-runtime", ui.layout.html)
        self.assertIn("seurat-interaction-runtime", ui.layout.html)
        self.assertIsInstance(ui.resize_runtime, ResizeRuntime)
        self.assertIn("seurat-resize-runtime", ui.layout.html)


if __name__ == "__main__":
    unittest.main()
