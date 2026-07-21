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


from ingest_campaign import (
    _build_schema_time_context,
    _interpret_campaign_schema,
    _schema_metadata_for_file,
)


class FakeReader:
    def __init__(self, values):
        self.values = values
        self.reads = []

    def read(self, path, step_selection=None):
        self.reads.append((path, step_selection))
        return np.asarray(self.values[path])


class CampaignSchemaTests(unittest.TestCase):
    def setUp(self):
        self.simulation_a = "runs/run-a/simulation"
        self.simulation_b = "runs/run-b/simulation"
        self.analysis_a = "runs/run-a/analysis"
        self.analysis_b = "runs/run-b/analysis"
        self.dataset_names = [
            self.simulation_b,
            self.analysis_a,
            "runs/run-a/simulation/visualizations/poloidal_P/frame-1.png",
            self.simulation_a,
            self.analysis_b,
            "schema.yaml",
        ]

    def test_append_patterns_match_multiple_datasets(self):
        schema = {
            "schema_version": 1,
            "name": "boutpp-selected-runs",
            "time": {"variable": "wtime"},
            "files": {
                "simulations": {
                    "role": "time_series",
                    "mode": "append",
                    "pattern": "runs/**/simulation",
                },
                "analyses": {
                    "role": "time_series",
                    "mode": "append",
                    "pattern": "runs/**/analysis",
                },
            },
        }

        layout = _interpret_campaign_schema(schema, self.dataset_names, {})

        self.assertEqual(
            layout["file_groups"]["simulations"]["datasets"],
            [self.simulation_a, self.simulation_b],
        )
        self.assertEqual(
            layout["file_groups"]["analyses"]["datasets"],
            [self.analysis_a, self.analysis_b],
        )
        self.assertEqual(layout["file_groups"]["simulations"]["time"], {"variable": "wtime"})
        self.assertEqual(layout["file_groups"]["analyses"]["time"], {"variable": "wtime"})

    def test_append_mode_requires_exactly_one_selector(self):
        for group in (
            {"role": "time_series", "mode": "append"},
            {
                "role": "time_series",
                "mode": "append",
                "path": self.simulation_a,
                "pattern": "runs/**/simulation",
            },
        ):
            with self.subTest(group=group):
                with self.assertRaisesRegex(ValueError, "exactly one of path or pattern"):
                    _interpret_campaign_schema(
                        {"schema_version": 1, "files": {"simulations": group}},
                        self.dataset_names,
                        {},
                    )

    def test_append_pattern_keeps_each_dataset_timeline_separate(self):
        schema = {
            "schema_version": 1,
            "time": {"variable": "wtime"},
            "files": {
                "simulations": {
                    "role": "time_series",
                    "mode": "append",
                    "pattern": "runs/**/simulation",
                },
            },
        }
        layout = _interpret_campaign_schema(schema, self.dataset_names, {})
        values = {
            f"{self.simulation_a}/wtime": [0.0, 0.5, 1.0],
            f"{self.simulation_b}/wtime": [10.0, 20.0],
        }
        reader = FakeReader(values)
        variables = {
            path: {"AvailableStepsCount": str(len(time_values))}
            for path, time_values in values.items()
        }

        context = _build_schema_time_context(layout, reader, variables)

        metadata_a = context["dataset_metadata"][self.simulation_a]
        metadata_b = context["dataset_metadata"][self.simulation_b]
        self.assertEqual(metadata_a["time_values"], [0.0, 0.5, 1.0])
        self.assertEqual(metadata_b["time_values"], [10.0, 20.0])
        self.assertEqual(metadata_a["schema_num_timesteps"], 3)
        self.assertEqual(metadata_b["schema_num_timesteps"], 2)
        self.assertEqual(
            _schema_metadata_for_file(context, self.simulation_a, frame_index=1)["physical_time"],
            0.5,
        )
        self.assertEqual(
            _schema_metadata_for_file(context, self.simulation_b, frame_index=1)["physical_time"],
            20.0,
        )
        self.assertEqual(
            {path for path, _ in reader.reads},
            set(values),
        )

    def test_exact_append_path_remains_supported(self):
        schema = {
            "schema_version": 1,
            "files": {
                "simulation": {
                    "role": "time_series",
                    "mode": "append",
                    "path": self.simulation_a,
                    "time": {"variable": "wtime"},
                },
            },
        }

        layout = _interpret_campaign_schema(schema, self.dataset_names, {})

        self.assertEqual(layout["file_groups"]["simulation"]["datasets"], [self.simulation_a])


if __name__ == "__main__":
    unittest.main()
