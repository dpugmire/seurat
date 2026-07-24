import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from db import CampaignDb, scalar_field_axis_spec, scalar_field_to_png_bytes
from seurat.controllers.visualization import VisualizationControllerMixin
from sqlite_store import SQLiteCampaignCollection


class ScalarFieldAxisTests(unittest.TestCase):
    def test_grid_metadata_produces_physical_axes(self):
        axes = scalar_field_axis_spec(
            {
                "shape": [256, 256],
                "grid": {
                    "axes": ["R", "Z"],
                    "bounds": {
                        "R": [0.2, 4.6],
                        "Z": [-2.5, 2.5],
                    },
                    "column_axis": "R",
                    "column_order": "ascending",
                    "row_axis": "Z",
                    "row_order": "descending",
                    "shape": [256, 256],
                },
            }
        )

        self.assertEqual(axes["x"]["label"], "R")
        self.assertEqual(axes["y"]["label"], "Z")
        self.assertEqual((axes["x"]["start"], axes["x"]["end"]), (0.2, 4.6))
        self.assertEqual((axes["y"]["start"], axes["y"]["end"]), (-2.5, 2.5))
        self.assertEqual(
            [tick["position"] for tick in axes["x"]["ticks"]],
            [0, 50, 100],
        )
        self.assertEqual(
            [tick["value"] for tick in axes["x"]["ticks"]],
            [0.2, 2.4, 4.6],
        )
        self.assertEqual(
            [tick["value"] for tick in axes["y"]["ticks"]],
            [-2.5, 0.0, 2.5],
        )

    def test_shape_only_metadata_uses_array_indices(self):
        axes = scalar_field_axis_spec({"shape": [3, 5]})

        self.assertEqual(axes["x"]["label"], "column")
        self.assertEqual(axes["y"]["label"], "row")
        self.assertEqual(
            [tick["value"] for tick in axes["x"]["ticks"]],
            [0.0, 2.0, 4.0],
        )
        self.assertEqual(
            [tick["value"] for tick in axes["y"]["ticks"]],
            [2.0, 1.0, 0.0],
        )

    def test_axes_are_attached_to_scalar_field_tiles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            collection = SQLiteCampaignCollection(
                Path(temp_dir) / "campaign.sqlite",
                "/campaign/example.aca",
            )
            collection.insert_one(
                {
                    "campaign_path": "/campaign/example.aca",
                    "variable_id": "fields/P",
                    "variable_name": "P",
                    "variable_type": "scalarField",
                    "payload_type": "SCALAR_FIELD",
                    "visualization_item_type": "SCALAR_FIELD",
                    "visualization_name": "scalar_field",
                    "source_dataset": "run/output.bp",
                    "frame_index": 0,
                    "scalar_field_metadata": {
                        "shape": [4, 6],
                        "grid": {
                            "column_axis": "R",
                            "row_axis": "Z",
                            "bounds": {
                                "R": [1.0, 3.0],
                                "Z": [-1.0, 1.0],
                            },
                            "row_order": "descending",
                        },
                    },
                }
            )
            campaign_db = CampaignDb(collection)

            with patch.object(
                campaign_db,
                "get_movie_frames_for_stream",
                return_value=([b"png"], 1, [0], [0], "timestep"),
            ):
                tiles = campaign_db.get_first_movie_tiles_for_variable(
                    "fields/P"
                )
            collection._con.close()

        self.assertEqual(len(tiles), 1)
        self.assertEqual(tiles[0]["scalar_field_axes"]["x"]["label"], "R")
        self.assertEqual(tiles[0]["scalar_field_axes"]["y"]["label"], "Z")


class ScalarFieldBackgroundTests(unittest.TestCase):
    @staticmethod
    def render(background=None):
        values = np.array(
            [
                [np.nan, 0.0],
                [1.0, np.nan],
            ],
            dtype=np.float32,
        )
        metadata = {
            "kind": "scalarField",
            "encoding": "raw",
            "compression": "none",
            "layout": "row-major",
            "value_encoding": "direct",
            "dtype": "float32",
            "byte_order": "little",
            "shape": [2, 2],
            "min": 0.0,
            "max": 1.0,
        }
        png = scalar_field_to_png_bytes(
            values.tobytes(),
            metadata,
            {"background": background} if background else {},
        )
        return Image.open(io.BytesIO(png)).convert("RGB")

    def test_non_finite_pixels_use_black_background_by_default(self):
        image = self.render()

        self.assertEqual(image.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(image.getpixel((1, 1)), (0, 0, 0))

    def test_non_finite_pixels_use_white_background_when_selected(self):
        image = self.render("white")

        self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(image.getpixel((1, 1)), (255, 255, 255))

    def test_background_setting_derives_contrasting_display_colors(self):
        controller = object.__new__(VisualizationControllerMixin)

        black = controller.normalize_scalar_field_settings(
            {"background": "black"}
        )
        white = controller.normalize_scalar_field_settings(
            {"background": "white"}
        )

        self.assertEqual(black["background_color"], "#000000")
        self.assertEqual(black["foreground_color"], "#ffffff")
        self.assertEqual(white["background_color"], "#ffffff")
        self.assertEqual(white["foreground_color"], "#111111")


if __name__ == "__main__":
    unittest.main()
