import unittest
from types import SimpleNamespace

from seurat.models.workspace_layout import (
    MAX_SPLIT_RATIO,
    MAX_WORKSPACE_PANES,
    MIN_SPLIT_RATIO,
    active_pane_and_tab,
    add_workspace_tab,
    apply_grid_snapshot,
    close_workspace_pane,
    close_workspace_tab,
    grid_snapshot,
    initial_workspace_layout,
    move_workspace_tab,
    reorder_workspace_tab,
    resize_workspace_split,
    split_workspace,
    workspace_geometry,
    workspace_pane_ids,
)
from seurat.state import init_state


class WorkspaceLayoutTests(unittest.TestCase):
    def make_state(self):
        state = SimpleNamespace()
        init_state(state, SimpleNamespace(ok=True, last_error=""))
        return state

    def test_grid_snapshot_round_trip_copies_mutable_values(self):
        state = self.make_state()
        state.gridCells[0]["variable_id"] = "density"

        snapshot = grid_snapshot(state)
        state.gridCells[0]["variable_id"] = "temperature"
        apply_grid_snapshot(state, snapshot)

        self.assertEqual(state.gridCells[0]["variable_id"], "density")
        self.assertIsNot(state.gridCells, snapshot["cells"])

    def test_new_tabs_keep_layout_preferences_but_start_empty(self):
        state = self.make_state()
        state.gridRows = 2
        state.gridCols = 2
        state.gridCells = state.gridCells[:4]
        state.gridCells[0]["variable_id"] = "density"
        layout = initial_workspace_layout(grid_snapshot(state))

        layout, tab_id = add_workspace_tab(layout, "pane-1", grid_snapshot(state))
        pane, tab = active_pane_and_tab(layout)

        self.assertEqual(tab_id, "tab-2")
        self.assertEqual(pane["active_tab_id"], tab_id)
        self.assertEqual((tab["grid"]["rows"], tab["grid"]["columns"]), (2, 2))
        self.assertEqual(len(tab["grid"]["cells"]), 4)
        self.assertTrue(
            all(not cell.get("variable_id") for cell in tab["grid"]["cells"])
        )

    def test_workspace_splits_active_panes_into_at_most_four_leaves(self):
        state = self.make_state()
        snapshot = grid_snapshot(state)
        layout = initial_workspace_layout(snapshot)

        layout, pane_id = split_workspace(layout, "vertical", snapshot)
        layout, third_pane_id = split_workspace(layout, "horizontal", snapshot)
        layout, fourth_pane_id = split_workspace(layout, "vertical", snapshot)
        layout, extra_pane_id = split_workspace(layout, "horizontal", snapshot)

        self.assertEqual(pane_id, "pane-2")
        self.assertEqual(third_pane_id, "pane-3")
        self.assertEqual(fourth_pane_id, "pane-4")
        self.assertIsNone(extra_pane_id)
        self.assertEqual(len(layout["panes"]), MAX_WORKSPACE_PANES)
        self.assertEqual(workspace_pane_ids(layout), tuple(
            f"pane-{index}" for index in range(1, 5)
        ))
        self.assertEqual(layout["split_direction"], "vertical")

    def test_workspace_can_split_a_specific_existing_pane(self):
        state = self.make_state()
        snapshot = grid_snapshot(state)
        layout = initial_workspace_layout(snapshot)
        layout, _ = split_workspace(layout, "horizontal", snapshot)

        layout, new_pane_id = split_workspace(
            layout, "vertical", snapshot, pane_id="pane-1"
        )

        self.assertEqual(new_pane_id, "pane-3")
        self.assertEqual(
            workspace_pane_ids(layout), ("pane-1", "pane-3", "pane-2")
        )
        frames, splitters = workspace_geometry(layout)
        self.assertEqual(set(frames), {"pane-1", "pane-2", "pane-3"})
        self.assertEqual(len(splitters), 2)
        self.assertAlmostEqual(frames["pane-1"]["height"], 50.0)
        self.assertAlmostEqual(frames["pane-3"]["top"], 50.0)

    def test_split_ratios_are_resized_and_clamped(self):
        state = self.make_state()
        snapshot = grid_snapshot(state)
        layout = initial_workspace_layout(snapshot)
        layout, _ = split_workspace(layout, "horizontal", snapshot)

        layout = resize_workspace_split(layout, "split-1", 0.7)
        frames, splitters = workspace_geometry(layout)

        self.assertAlmostEqual(layout["root"]["ratio"], 0.7)
        self.assertAlmostEqual(frames["pane-1"]["width"], 70.0)
        self.assertAlmostEqual(splitters[0]["left"], 70.0)
        self.assertEqual(
            resize_workspace_split(layout, "split-1", 0)["root"]["ratio"],
            MIN_SPLIT_RATIO,
        )
        self.assertEqual(
            resize_workspace_split(layout, "split-1", 1)["root"]["ratio"],
            MAX_SPLIT_RATIO,
        )

    def test_tabs_move_between_panes_without_losing_their_grid(self):
        state = self.make_state()
        snapshot = grid_snapshot(state)
        layout = initial_workspace_layout(snapshot)
        layout, moved_tab_id = add_workspace_tab(layout, "pane-1", snapshot)
        _, moved_tab = active_pane_and_tab(layout)
        moved_tab["grid"]["cells"][0]["variable_id"] = "pressure"
        layout, _ = split_workspace(layout, "horizontal", snapshot)

        layout = move_workspace_tab(layout, "pane-1", moved_tab_id)
        pane, tab = active_pane_and_tab(layout)

        self.assertEqual(pane["id"], "pane-2")
        self.assertEqual(tab["id"], moved_tab_id)
        self.assertEqual(tab["grid"]["cells"][0]["variable_id"], "pressure")

    def test_tabs_reorder_within_a_pane_without_losing_state(self):
        state = self.make_state()
        snapshot = grid_snapshot(state)
        layout = initial_workspace_layout(snapshot)
        layout, _ = add_workspace_tab(layout, "pane-1", snapshot)
        layout, active_tab_id = add_workspace_tab(layout, "pane-1", snapshot)
        for index, tab in enumerate(layout["panes"][0]["tabs"]):
            tab["grid"]["cells"][0]["variable_id"] = f"variable-{index + 1}"

        layout = reorder_workspace_tab(layout, "pane-1", "tab-1", 3)

        tabs = layout["panes"][0]["tabs"]
        self.assertEqual([tab["id"] for tab in tabs], ["tab-2", "tab-3", "tab-1"])
        self.assertEqual(
            [tab["grid"]["cells"][0]["variable_id"] for tab in tabs],
            ["variable-2", "variable-3", "variable-1"],
        )
        self.assertEqual(layout["active_tab_id"], active_tab_id)
        self.assertEqual(layout["panes"][0]["active_tab_id"], active_tab_id)

    def test_closing_a_pane_merges_its_tabs_into_the_remaining_pane(self):
        state = self.make_state()
        snapshot = grid_snapshot(state)
        layout = initial_workspace_layout(snapshot)
        layout, _ = split_workspace(layout, "horizontal", snapshot)

        layout = close_workspace_pane(layout, "pane-2")

        self.assertEqual(len(layout["panes"]), 1)
        self.assertEqual(len(layout["panes"][0]["tabs"]), 2)
        self.assertEqual(layout["split_direction"], "none")

    def test_closing_nested_pane_promotes_its_sibling_subtree(self):
        state = self.make_state()
        snapshot = grid_snapshot(state)
        layout = initial_workspace_layout(snapshot)
        layout, _ = split_workspace(layout, "horizontal", snapshot)
        layout, _ = split_workspace(
            layout, "vertical", snapshot, pane_id="pane-1"
        )

        layout = close_workspace_pane(layout, "pane-1")

        self.assertEqual(workspace_pane_ids(layout), ("pane-3", "pane-2"))
        self.assertEqual(len(layout["panes"]), 2)
        self.assertEqual(layout["root"]["direction"], "horizontal")
        pane_three = next(
            pane for pane in layout["panes"] if pane["id"] == "pane-3"
        )
        self.assertEqual(len(pane_three["tabs"]), 2)

    def test_at_least_one_tab_is_always_retained(self):
        state = self.make_state()
        snapshot = grid_snapshot(state)
        layout = initial_workspace_layout(snapshot)

        unchanged = close_workspace_tab(layout, "pane-1", "tab-1")

        self.assertEqual(unchanged, layout)


if __name__ == "__main__":
    unittest.main()
