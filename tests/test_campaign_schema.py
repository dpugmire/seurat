import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path

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
    _load_campaign_schema,
    _read_campaign_schema_text,
    _schema_metadata_for_file,
    _schema_metadata_for_variable,
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

    def test_external_campaign_schema_preserves_file_group_pattern(self):
        datasets = ["xgc.3d.00010.bp", "xgc.3d.00012.bp"]
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_path = Path(temp_dir) / "schema.yaml"
            schema_path.write_text(
                """
schema_version: 1
name: code_xgc
files:
  xgc_3d:
    role: time_series
    mode: file_per_timestep
    pattern: xgc.3d.*.bp
    step_from_filename: 'xgc\\.3d\\.(\\d+)\\.bp'
""".strip(),
                encoding="utf-8",
            )

            layout = _load_campaign_schema(
                "/campaign/without-embedded-schema.aca",
                datasets,
                {},
                campaign_schema_path=str(schema_path),
            )

        group = layout["file_groups"]["xgc_3d"]
        self.assertEqual(group["pattern"], "xgc.3d.*.bp")
        context = _build_schema_time_context(layout, FakeReader({}), {})
        self.assertEqual(
            context["dataset_metadata"][datasets[0]]["schema_pattern"],
            "xgc.3d.*.bp",
        )

    def test_canonical_embedded_schema_takes_precedence_over_legacy_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaign_path = Path(temp_dir) / "campaign.aca"
            con = sqlite3.connect(campaign_path)
            con.executescript(
                """
                create table dataset (
                    rowid integer primary key,
                    name text,
                    fileformat text,
                    deltime integer
                );
                create table replica (
                    rowid integer primary key,
                    datasetid integer,
                    keyid integer,
                    deltime integer
                );
                create table repfiles (replicaid integer, fileid integer);
                create table file (
                    fileid integer primary key,
                    compression integer,
                    data blob
                );
                """
            )
            for rowid, name, text in (
                (1, "schema.yaml", "name: legacy\n"),
                (2, "__campaign_schema.yaml", "name: canonical\n"),
            ):
                con.execute(
                    "insert into dataset(rowid, name, fileformat, deltime) "
                    "values (?, ?, 'TEXT', 0)",
                    (rowid, name),
                )
                con.execute(
                    "insert into replica(rowid, datasetid, keyid, deltime) "
                    "values (?, ?, 0, 0)",
                    (rowid, rowid),
                )
                con.execute(
                    "insert into file(fileid, compression, data) values (?, 0, ?)",
                    (rowid, text.encode("utf-8")),
                )
                con.execute(
                    "insert into repfiles(replicaid, fileid) values (?, ?)",
                    (rowid, rowid),
                )
            con.commit()
            con.close()

            schema_text = _read_campaign_schema_text(str(campaign_path))

        self.assertEqual(schema_text, "name: canonical\n")

    def test_m3dc1_variable_groups_use_independent_axes(self):
        dataset = "fwz3_2d_mgi3.rs4.bp"
        schema = {
            "schema_version": 1,
            "name": "code_m3dc1",
            "files": {
                "output": {
                    "role": "time_series",
                    "mode": "append",
                    "path": dataset,
                }
            },
            "axes": {
                "field_time": {
                    "file": "output",
                    "variable": "metadata/time_values",
                    "kind": "time",
                },
                "scalar_time": {
                    "file": "output",
                    "variable": "scalars/time",
                    "kind": "time",
                },
                "simulation_timestep": {
                    "file": "output",
                    "variable": "metadata/ntimesteps",
                    "kind": "timestep_index",
                },
            },
            "meshes": {
                "mesh": {
                    "file": "output",
                    "variable": "mesh/elements",
                    "model": "m3dc1_2d_unstructured_elements",
                }
            },
            "basis": {
                "basis": {
                    "file": "output",
                    "variables": {
                        "mi": "basis/mi",
                        "ni": "basis/ni",
                    },
                    "model": "m3dc1_reduced_quintic_2d_basis",
                }
            },
            "variable_groups": {
                "fields": {
                    "file": "output",
                    "pattern": "fields/*",
                    "role": "field",
                    "data_model": "m3dc1_element_basis_coefficients",
                    "mesh": "mesh",
                    "basis": "basis",
                    "time_axis": "field_time",
                    "timestep_axis": "simulation_timestep",
                },
                "equilibrium_fields": {
                    "file": "output",
                    "pattern": "equilibrium/fields/*",
                    "role": "field",
                    "data_model": "m3dc1_element_basis_coefficients",
                    "mesh": "mesh",
                    "basis": "basis",
                    "static": True,
                },
                "scalars": {
                    "file": "output",
                    "pattern": "scalars/*",
                    "role": "scalar_trace",
                    "x_axis": "scalar_time",
                },
                "pellet": {
                    "file": "output",
                    "pattern": "pellet/*",
                    "role": "pellet_trace",
                    "x_axis": "scalar_time",
                },
            },
            "visualization_templates": [
                {
                    "name": "P_2d",
                    "kind": "field_2d",
                    "variables": [
                        {"role": "color-by", "variable": "fields/P"}
                    ],
                }
            ],
        }
        values = {
            f"{dataset}/metadata/time_values": [0.0, 100.0],
            f"{dataset}/metadata/ntimesteps": [0, 50],
            f"{dataset}/scalars/time": [0.0, 50.0, 100.0],
        }
        variables = {
            **{
                path: {"AvailableStepsCount": "1"}
                for path in values
            },
            f"{dataset}/mesh/elements": {},
            f"{dataset}/basis/mi": {},
            f"{dataset}/basis/ni": {},
            f"{dataset}/fields/P": {"AvailableStepsCount": "2"},
            f"{dataset}/equilibrium/fields/P": {"AvailableStepsCount": "1"},
            f"{dataset}/scalars/toroidal_current": {"AvailableStepsCount": "1"},
            f"{dataset}/pellet/pellet_r": {"AvailableStepsCount": "1"},
        }
        layout = _interpret_campaign_schema(schema, [dataset], {})
        context = _build_schema_time_context(
            layout,
            FakeReader(values),
            variables,
        )

        field = _schema_metadata_for_variable(
            context,
            dataset,
            "fields/P",
            frame_index=1,
            include_time_values=False,
        )
        scalar = _schema_metadata_for_variable(
            context,
            dataset,
            "scalars/toroidal_current",
        )
        equilibrium = _schema_metadata_for_variable(
            context,
            dataset,
            "equilibrium/fields/P",
        )
        pellet = _schema_metadata_for_variable(
            context,
            dataset,
            "pellet/pellet_r",
        )

        self.assertEqual(field["variable_group"], "fields")
        self.assertEqual(field["physical_time"], 100.0)
        self.assertEqual(field["simulation_timestep"], 50.0)
        self.assertEqual(field["data_model"], "m3dc1_element_basis_coefficients")
        self.assertEqual(scalar["variable_group"], "scalars")
        self.assertEqual(scalar["time_values"], [0.0, 50.0, 100.0])
        self.assertEqual(pellet["variable_group"], "pellet")
        self.assertEqual(pellet["x_axis_variable"], "scalars/time")
        self.assertEqual(equilibrium["variable_group"], "equilibrium_fields")
        self.assertTrue(equilibrium["static"])
        self.assertNotIn("time_values", equilibrium)
        self.assertNotIn("physical_time", equilibrium)

    def test_variable_group_patterns_match_full_paths(self):
        schema = {
            "schema_version": 1,
            "files": {
                "output": {
                    "role": "time_series",
                    "mode": "append",
                    "path": "run.bp",
                }
            },
            "variable_groups": {
                "fields": {
                    "file": "output",
                    "pattern": "fields/*",
                    "role": "field",
                },
                "equilibrium_fields": {
                    "file": "output",
                    "pattern": "equilibrium/fields/*",
                    "role": "field",
                    "static": True,
                },
            },
        }
        variables = {
            "run.bp/fields/P": {},
            "run.bp/equilibrium/fields/P": {},
        }
        layout = _interpret_campaign_schema(schema, ["run.bp"], {})
        context = _build_schema_time_context(
            layout,
            FakeReader({}),
            variables,
        )

        self.assertEqual(
            context["variable_metadata"]["run.bp"]["fields/P"]["variable_group"],
            "fields",
        )
        self.assertEqual(
            context["variable_metadata"]["run.bp"]["equilibrium/fields/P"][
                "variable_group"
            ],
            "equilibrium_fields",
        )


if __name__ == "__main__":
    unittest.main()
