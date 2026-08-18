import sqlite3
from pathlib import Path

import numpy as np
import pytest

from db import CampaignDb
from ingest_campaign import _load_unified_representation_index, parse_campaign
from plugin_runtime import render_plugin_tile
from seurat.demo_campaign import (
    DEMO_SOURCES,
    DEMO_VARIABLES_1D,
    DEMO_VARIABLES_2D,
    DemoConfig,
    analytical_step,
    generate_demo_campaign,
    temporary_demo_campaign,
)
from sqlite_store import open_sqlite_collection


def test_analytical_fields_are_deterministic_and_time_varying():
    config = DemoConfig(steps=4, samples_1d=24, shape_2d=(10, 12))
    first = analytical_step(DEMO_SOURCES[0], 0, config)
    again = analytical_step(DEMO_SOURCES[0], 0, config)
    later = analytical_step(DEMO_SOURCES[0], 1, config)

    assert set(first) == set((*DEMO_VARIABLES_1D, *DEMO_VARIABLES_2D))
    for name in DEMO_VARIABLES_1D:
        assert first[name].shape == (24,)
    for name in DEMO_VARIABLES_2D:
        assert first[name].shape == (10, 12)
    for name, values in first.items():
        assert values.dtype == np.float32
        assert np.all(np.isfinite(values))
        np.testing.assert_array_equal(values, again[name])
        assert not np.array_equal(values, later[name])


def test_source_parameter_sets_produce_distinct_fields():
    config = DemoConfig(steps=3, samples_1d=16, shape_2d=(8, 8))
    baseline = analytical_step(DEMO_SOURCES[0], 1, config)
    for source in DEMO_SOURCES[1:]:
        candidate = analytical_step(source, 1, config)
        assert any(
            not np.array_equal(baseline[name], candidate[name])
            for name in baseline
        )


def test_demo_config_rejects_degenerate_dimensions():
    with pytest.raises(ValueError, match="steps"):
        DemoConfig(steps=1).validate()
    with pytest.raises(ValueError, match="1D"):
        DemoConfig(samples_1d=1).validate()
    with pytest.raises(ValueError, match="2D"):
        DemoConfig(shape_2d=(8, 1)).validate()


def test_generated_demo_archive_and_ingestion(tmp_path: Path):
    pytest.importorskip("hpc_campaign")
    config = DemoConfig(steps=3, samples_1d=16, shape_2d=(8, 10))
    demo = generate_demo_campaign(tmp_path, config=config)

    assert demo.campaign_path.is_file()
    assert sorted(path.name for path in (tmp_path / "sources").glob("*.bp")) == [
        f"{source.name}.bp" for source in sorted(DEMO_SOURCES, key=lambda item: item.name)
    ]

    con = sqlite3.connect(demo.campaign_path)
    try:
        source_count = con.execute(
            "select count(*) from dataset where name like 'sources/%.bp' and deltime = 0"
        ).fetchone()[0]
        variable_count = con.execute(
            "select count(*) from logical_variable"
        ).fetchone()[0]
        chunk_count = con.execute(
            "select count(*) from variable_chunk"
        ).fetchone()[0]
    finally:
        con.close()

    assert source_count == 5
    assert variable_count == 60
    assert chunk_count == 90

    representation_index = _load_unified_representation_index(
        str(demo.campaign_path)
    )
    assert len(representation_index) == 90
    assert {
        entry["item_type"] for entry in representation_index.values()
    } == {"IMAGE", "SCALAR_FIELD"}

    collection = open_sqlite_collection(
        str(demo.campaign_path),
        db_path=str(demo.sidecar_path),
    )
    try:
        parse_campaign(str(demo.campaign_path), collection)
        db = CampaignDb(collection)
        assert set(db.distinct_variable_names()) == set(
            (*DEMO_VARIABLES_1D, *DEMO_VARIABLES_2D)
        )
        for variable_name in (*DEMO_VARIABLES_1D, *DEMO_VARIABLES_2D):
            assert len(db.variable_min_max_summary(variable_name)["sources"]) == 5

        profile_candidate = db.scalar_plot_candidate(
            "traveling_wave_1d",
            source_filter={"source_dataset": "sources/baseline.bp"},
        )
        assert profile_candidate
        profile_tile = render_plugin_tile(
            str(demo.campaign_path),
            "profile_timeseries",
            profile_candidate,
        )
        assert profile_tile["media_type"] == "plot1d"
        assert profile_tile["plot"]["x_label"] == "adios_step"
        assert len(profile_tile["plot"]["series"]) == 5

        for variable_name in DEMO_VARIABLES_2D:
            assert db.distinct_visualization_names_for_variable(variable_name) == [
                "heatmap",
                "scalar_field",
            ]
            scalar_docs = list(
                collection.find(
                    {
                        "variable_id": variable_name,
                        "variable_type": "scalarField",
                    }
                )
            )
            assert len(scalar_docs) == 15
            assert {doc["frame_index"] for doc in scalar_docs} == {0, 1, 2}
            assert all(doc["association_source"] == "unified-variable" for doc in scalar_docs)

        image_frames, image_total, image_indices, _, _ = (
            db.get_movie_frames_for_stream(
                "moving_blob_2d",
                "heatmap",
                "",
                "",
                source_dataset="sources/baseline.bp",
            )
        )
        assert image_total == 3
        assert image_indices == [0, 1, 2]
        assert all(frame.startswith(b"\x89PNG\r\n\x1a\n") for frame in image_frames)

        scalar_frames, total, frame_indices, time_values, time_mode = (
            db.get_movie_frames_for_stream(
                "moving_blob_2d",
                "scalar_field",
                "",
                "",
                source_dataset="sources/baseline.bp",
            )
        )
        assert total == 3
        assert frame_indices == [0, 1, 2]
        assert time_values == [0.0, 1.0, 2.0]
        assert time_mode == "timestep"
        assert all(frame.startswith(b"\x89PNG\r\n\x1a\n") for frame in scalar_frames)
    finally:
        collection.close()


def test_temporary_demo_campaign_removes_generated_files():
    pytest.importorskip("hpc_campaign")
    config = DemoConfig(steps=2, samples_1d=8, shape_2d=(4, 4))
    with temporary_demo_campaign(config=config) as demo:
        root = demo.root
        assert demo.campaign_path.exists()
    assert not root.exists()
