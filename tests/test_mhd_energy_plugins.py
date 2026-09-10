import sys
import types
import unittest

import numpy as np


try:
    import adios2  # noqa: F401
except ModuleNotFoundError:
    adios2 = types.ModuleType("adios2")
    adios2.FileReader = object
    sys.modules["adios2"] = adios2


from plugin_runtime import discover_plugins, plot1d_payload, plugin_options_schema
from seurat_plugins import mhd_energy_conservation as conservation
from seurat_plugins import mhd_energy_partition as partition


class FakeHelpers:
    def __init__(self, data):
        self.data = {name: np.asarray(values) for name, values in data.items()}

    def read_source_variable(self, name, step_selection=None):
        if name not in self.data:
            raise KeyError(name)
        values = self.data[name]
        if step_selection is None:
            return values
        start, count = step_selection
        return values[start : start + count]

    def plot1d_payload(self, series_values, x_label, y_label):
        return plot1d_payload(series_values, x_label=x_label, y_label=y_label)


def scalar_meta(name):
    return {
        "variable_name": name,
        "variable_id": name,
        "variable_path": f"source/{name}",
        "ndims": 0,
        "steps_count": 3,
    }


def context(data, options=None):
    return {
        **scalar_meta("total_energy"),
        "helpers": FakeHelpers(data),
        "options": dict(options or {}),
    }


class MhdEnergyPluginTests(unittest.TestCase):
    def test_plugins_are_registered(self):
        discovered = {info.plugin_id for info in discover_plugins()}

        self.assertIn(conservation.PLUGIN_ID, discovered)
        self.assertIn(partition.PLUGIN_ID, discovered)

    def test_plugins_support_scalar_energy_timeseries(self):
        for name in (
            "total_energy",
            "internal_energy",
            "kinetic_energy",
            "magnetic_energy",
        ):
            with self.subTest(name=name):
                self.assertTrue(conservation.supports(scalar_meta(name)))
                self.assertTrue(partition.supports(scalar_meta(name)))

        self.assertFalse(conservation.supports(scalar_meta("mass")))
        self.assertFalse(
            partition.supports({**scalar_meta("total_energy"), "steps_count": 1})
        )
        self.assertFalse(
            partition.supports({**scalar_meta("total_energy"), "ndims": 1})
        )

    def test_options_use_select_controls(self):
        conservation_schema = {
            item["key"]: item
            for item in plugin_options_schema(
                conservation.PLUGIN_ID,
                scalar_meta("total_energy"),
            )
        }
        partition_schema = {
            item["key"]: item
            for item in plugin_options_schema(
                partition.PLUGIN_ID,
                scalar_meta("total_energy"),
            )
        }

        self.assertEqual(
            conservation_schema["x_axis"]["choices"],
            ["time", "step", "adios_step"],
        )
        self.assertEqual(
            partition_schema["denominator"]["choices"],
            ["total_energy", "component_sum"],
        )

    def test_conservation_plots_relative_total_energy_drift(self):
        tile = conservation.render(
            context(
                {
                    "time": [0.0, 0.5, 1.0],
                    "total_energy": [10.0, 11.0, 9.0],
                    "internal_energy": [5.0, 5.5, 4.0],
                    "kinetic_energy": [3.0, 3.0, 3.0],
                    "magnetic_energy": [2.0, 2.0, 2.0],
                },
                {"x_axis": "time", "show_component_residual": True},
            )
        )

        self.assertEqual(tile["media_type"], "plot1d")
        self.assertEqual(tile["plot"]["x_label"], "time")
        self.assertEqual(tile["plot"]["y_label"], "relative energy error")
        self.assertEqual(len(tile["plot"]["series"]), 2)
        np.testing.assert_allclose(
            tile["plot"]["series"][0]["y"],
            [0.0, 0.1, -0.1],
        )
        np.testing.assert_allclose(
            tile["plot"]["series"][1]["y"],
            [0.0, 0.5 / 11.0, 0.0],
        )

    def test_conservation_residual_is_optional_when_components_are_missing(self):
        tile = conservation.render(
            context(
                {
                    "time": [0.0, 0.5, 1.0],
                    "total_energy": [10.0, 11.0, 9.0],
                },
                {"x_axis": "time", "show_component_residual": True},
            )
        )

        self.assertEqual(len(tile["plot"]["series"]), 1)
        self.assertIn("component residual unavailable", tile["note"])

    def test_partition_plots_component_fractions_of_total_energy(self):
        tile = partition.render(
            context(
                {
                    "time": [0.0, 0.5, 1.0],
                    "total_energy": [10.0, 10.0, 10.0],
                    "internal_energy": [5.0, 6.0, 7.0],
                    "kinetic_energy": [3.0, 3.0, 3.0],
                    "magnetic_energy": [2.0, 1.0, 0.0],
                },
                {"x_axis": "time", "denominator": "total_energy"},
            )
        )

        self.assertEqual(tile["media_type"], "plot1d")
        self.assertEqual(tile["plot"]["y_label"], "energy fraction")
        self.assertEqual(len(tile["plot"]["series"]), 3)
        np.testing.assert_allclose(tile["plot"]["series"][0]["y"], [0.5, 0.6, 0.7])
        np.testing.assert_allclose(tile["plot"]["series"][1]["y"], [0.3, 0.3, 0.3])
        np.testing.assert_allclose(tile["plot"]["series"][2]["y"], [0.2, 0.1, 0.0])

    def test_partition_falls_back_to_component_sum_when_total_is_missing(self):
        tile = partition.render(
            context(
                {
                    "time": [0.0, 0.5, 1.0],
                    "internal_energy": [5.0, 6.0, 7.0],
                    "kinetic_energy": [3.0, 3.0, 3.0],
                    "magnetic_energy": [2.0, 1.0, 0.0],
                },
                {"x_axis": "time", "denominator": "total_energy"},
            )
        )

        self.assertIn("denominator: component sum", tile["note"])
        np.testing.assert_allclose(tile["plot"]["series"][0]["y"], [0.5, 0.6, 0.7])


if __name__ == "__main__":
    unittest.main()
