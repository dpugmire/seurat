import unittest
from types import SimpleNamespace

from seurat.models.workspace_layout import (
    active_pane_and_tab,
    add_workspace_tab,
    apply_grid_snapshot,
    close_workspace_pane,
    close_workspace_tab,
    grid_snapshot,
    initial_workspace_layout,
    move_workspace_tab,
    reorder_workspace_tab,
    split_workspace,
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

    def test_workspace_splits_into_at_most_two_panes(self):
        state = self.make_state()
        snapshot = grid_snapshot(state)
        layout = initial_workspace_layout(snapshot)

        layout, pane_id = split_workspace(layout, "vertical", snapshot)
        layout, extra_pane_id = split_workspace(layout, "horizontal", snapshot)

        self.assertEqual(pane_id, "pane-2")
        self.assertIsNone(extra_pane_id)
        self.assertEqual(len(layout["panes"]), 2)
        self.assertEqual(layout["split_direction"], "horizontal")

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

    def test_at_least_one_tab_is_always_retained(self):
        state = self.make_state()
        snapshot = grid_snapshot(state)
        layout = initial_workspace_layout(snapshot)

        unchanged = close_workspace_tab(layout, "pane-1", "tab-1")

        self.assertEqual(unchanged, layout)


if __name__ == "__main__":
    unittest.main()
