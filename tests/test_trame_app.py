import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from trame.app import TrameComponent, get_server

import app as compatibility_app
from seurat.app import SeuratApp, build_parser
from seurat import module as seurat_module
from seurat.components import SeuratUI
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
                controller_attacher=attach,
                ui_builder=build,
            )

        self.assertIs(app.server, server)
        self.assertIs(app.collection, collection)
        self.assertIs(app.db, db)
        self.assertIs(app.refresh_variable_list, refresh_variable_list)
        self.assertIs(app.ui, built_ui)
        self.assertEqual(
            server.state.trame__scripts,
            [f"{seurat_module.BASE_URL}/seurat.js"],
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
        self.assertIs(controller_calls[0]["db"], db)
        self.assertIs(controller_calls[0]["collection"], collection)
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

    def test_ui_is_composed_from_trame_components(self):
        server = get_server(
            f"seurat-ui-components-{id(self)}",
            client_type="vue3",
        )

        ui = build_ui(server, campaign_name="sample.aca")

        self.assertIsInstance(ui, SeuratUI)
        for component in (
            ui.query_toolbar,
            ui.help_dialog,
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

        self.assertIn("Campaign loaded: sample.aca", ui.layout.html)
        self.assertIn('id="seurat-variable-column"', ui.layout.html)
        self.assertIn('id="seurat-context-menu"', ui.layout.html)


if __name__ == "__main__":
    unittest.main()
