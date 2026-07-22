"""Characterize Seurat behavior in a mounted Vue client."""

import io
import os

import pytest
from PIL import Image


pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("SEURAT_RUN_BROWSER_TESTS") != "1",
        reason="set SEURAT_RUN_BROWSER_TESTS=1 to run browser tests",
    ),
]


def _open_app(page, seurat_server, mode="step"):
    console_errors = []
    page_errors = []
    response_errors = []
    page.on(
        "console",
        lambda message: (
            console_errors.append(message.text) if message.type == "error" else None
        ),
    )
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "response",
        lambda response: (
            response_errors.append(
                f"{response.status} {response.request.method} {response.url}"
            )
            if response.status >= 400
            else None
        ),
    )
    page.goto(seurat_server(mode), wait_until="networkidle")
    page.locator("#seurat-variable-column").wait_for(state="visible")
    return console_errors, page_errors, response_errors


def test_app_mounts_and_renders_structural_ui(page, seurat_server):
    console_errors, page_errors, response_errors = _open_app(page, seurat_server)

    assert page.get_by_text("Campaign loaded: browser-step.aca").is_visible()
    assert page.locator('[title="fixture/scalars.bp/internal_energy"]').is_visible()
    assert page.locator('[title="fixture/images/current_z"]').is_visible()
    assert page.locator(".seurat-plot1d svg").is_visible()
    page.locator('[data-seurat-grid-runtime="mounted"]').wait_for(state="attached")
    page.locator('[data-seurat-interaction-runtime="mounted"]').wait_for(
        state="attached"
    )
    assert (
        page.locator(
            '.seurat-content-column[data-seurat-grid-runtime-owner="mounted"]'
        ).count()
        == 1
    )
    assert (
        page.locator(
            '.v-application[data-seurat-interaction-runtime-owner="mounted"]'
        ).count()
        == 1
    )

    rendered = page.locator(".seurat-content-column").screenshot()
    image = Image.open(io.BytesIO(rendered)).convert("RGB")
    assert image.width >= 500
    assert image.height >= 300
    assert len(image.getcolors(maxcolors=image.width * image.height) or []) > 8

    assert page_errors == []
    assert console_errors == [], response_errors


def test_variable_group_expands_and_collapses(page, seurat_server):
    _open_app(page, seurat_server)

    group = page.get_by_role("button", name="▾0D", exact=True)
    variable = page.locator('[title="fixture/scalars.bp/internal_energy"]')
    assert variable.is_visible()

    group.click()
    variable.wait_for(state="hidden")
    collapsed_group = page.get_by_role("button", name="▸0D", exact=True)
    assert collapsed_group.get_attribute("aria-expanded") == "false"

    collapsed_group.click()
    variable.wait_for(state="visible")
    expanded_group = page.get_by_role("button", name="▾0D", exact=True)
    assert expanded_group.get_attribute("aria-expanded") == "true"


def test_grid_selection_assignment_and_layout_controls(page, seurat_server):
    _open_app(page, seurat_server)

    empty_cell = page.locator('.seurat-dropcell[data-cell-index="2"]')
    empty_cell.click()
    page.wait_for_function(
        "document.querySelector('.seurat-dropcell[data-cell-index=\"2\"]')"
        ".getAttribute('data-cell-active') === '1'"
    )

    variable = page.locator('[data-item="current_z"]')
    variable.drag_to(empty_cell)
    page.wait_for_function(
        "document.querySelector('.seurat-dropcell[data-cell-index=\"2\"]')"
        ".getAttribute('data-cell-filled') === '1'"
    )
    assert empty_cell.get_by_text("current_z", exact=True).is_visible()

    page.get_by_role("button", name="Settings", exact=True).click()
    page.get_by_role("button", name="Grid size 1 x 3 ▾", exact=True).click()
    page.get_by_role("button", name="2 x 2", exact=True).click()
    page.wait_for_function("document.querySelectorAll('.seurat-dropcell').length === 4")


def test_cell_context_menu_opens(page, seurat_server):
    _open_app(page, seurat_server)

    cell = page.locator('.seurat-dropcell[data-cell-index="0"]')
    cell.click(button="right")

    menu = page.locator("#seurat-context-menu")
    menu.wait_for(state="visible")
    assert menu.get_by_text("internal_energy", exact=True).is_visible()
    assert menu.get_by_text("Select Cell", exact=True).is_visible()


def test_variable_context_menu_opens(page, seurat_server):
    _open_app(page, seurat_server)

    variable = page.locator('[data-item="internal_energy"]')
    variable.click(button="right")

    menu = page.locator("#seurat-context-menu")
    menu.wait_for(state="visible")
    assert menu.get_by_text("internal_energy", exact=True).is_visible()
    assert menu.get_by_text("Add To Grid", exact=True).is_visible()
    assert menu.get_by_text("Select Variable", exact=True).is_visible()


def test_grid_cell_drag_moves_content(page, seurat_server):
    _open_app(page, seurat_server)

    source = page.locator('.seurat-dropcell[data-cell-index="0"]')
    target = page.locator('.seurat-dropcell[data-cell-index="2"]')
    source.drag_to(target)

    page.wait_for_function(
        "document.querySelector('.seurat-dropcell[data-cell-index=\"0\"]')"
        ".getAttribute('data-cell-filled') === '0'"
    )
    assert target.get_by_text("internal_energy", exact=True).is_visible()


def test_interaction_runtime_releases_and_restores_handlers(page, seurat_server):
    _open_app(page, seurat_server)

    root = page.locator(".v-application")
    menu = page.locator("#seurat-context-menu")
    cell = page.locator('.seurat-dropcell[data-cell-index="0"]')

    root.evaluate("root => window.seuratInteractionRuntime.unmount(root)")
    assert root.get_attribute("data-seurat-interaction-runtime-owner") is None
    cell.click(button="right")
    assert not menu.is_visible()

    root.evaluate("root => window.seuratInteractionRuntime.mount(root)")
    root.evaluate("root => window.seuratInteractionRuntime.mount(root)")
    assert root.get_attribute("data-seurat-interaction-runtime-owner") == "mounted"
    page.evaluate(
        """() => {
            const originalTrigger = window.trame.trigger.bind(window.trame);
            window.__seuratInteractionTriggerCounts = {};
            window.trame.trigger = (name, args) => {
                const counts = window.__seuratInteractionTriggerCounts;
                counts[name] = (counts[name] || 0) + 1;
                return originalTrigger(name, args);
            };
        }"""
    )
    cell.click(button="right")
    menu.wait_for(state="visible")
    assert menu.get_by_text("internal_energy", exact=True).is_visible()
    assert (
        page.evaluate("window.__seuratInteractionTriggerCounts.show_cell_context_menu")
        == 1
    )


def test_grid_runtime_releases_and_restores_timeline_handlers(page, seurat_server):
    _open_app(page, seurat_server)

    root = page.locator(".seurat-content-column")
    label = page.locator("#seurat-vcr-time-value")
    forward = page.get_by_title("Forward step")

    root.evaluate("root => window.seuratGridRuntime.unmount(root)")
    assert root.get_attribute("data-seurat-grid-runtime-owner") is None
    forward.click()
    assert label.text_content() == "Step = 0"

    root.evaluate("root => window.seuratGridRuntime.mount(root)")
    assert root.get_attribute("data-seurat-grid-runtime-owner") == "mounted"
    forward.click()
    page.wait_for_function(
        "document.querySelector('#seurat-vcr-time-value').textContent === 'Step = 1'"
    )


def test_schema_less_timeline_uses_step_indices(page, seurat_server):
    _open_app(page, seurat_server, mode="step")

    label = page.locator("#seurat-vcr-time-value")
    image = page.locator('img[data-grid-image-sequence="1"]')
    label.wait_for(state="visible")
    assert label.text_content() == "Step = 0"
    assert image.get_attribute("data-current-frame") == "0"

    page.get_by_title("Forward step").click()

    page.wait_for_function(
        "document.querySelector('#seurat-vcr-time-value').textContent === 'Step = 1'"
    )
    assert image.get_attribute("data-current-frame") == "1"


def test_schema_less_timeline_cursor_uses_step_not_normalized_progress(
    page, seurat_server
):
    _open_app(page, seurat_server, mode="step")

    slider = page.locator("#seurat-vcr-step-slider")
    image = page.locator('img[data-grid-image-sequence="1"]')
    slider.evaluate(
        """element => {
            element.value = "30";
            element.dispatchEvent(new Event("input", { bubbles: true }));
        }"""
    )
    page.wait_for_function(
        "document.querySelector('#seurat-vcr-time-value').textContent === 'Step = 30'"
    )

    assert image.get_attribute("data-current-frame") == "30"
    frame = page.locator(".seurat-plot1d svg rect").first
    cursor = page.locator(".seurat-plot1d-cursor-line")
    frame_x = float(frame.get_attribute("x"))
    frame_width = float(frame.get_attribute("width"))
    cursor_x = float(cursor.get_attribute("x1"))
    cursor_progress = (cursor_x - frame_x) / frame_width
    assert cursor_progress == pytest.approx(30.0 / 79.0, abs=0.01)


def test_physical_timeline_uses_declared_time_values(page, seurat_server):
    _open_app(page, seurat_server, mode="physical")

    label = page.locator("#seurat-vcr-time-value")
    image = page.locator('img[data-grid-image-sequence="1"]')
    label.wait_for(state="visible")
    assert label.text_content() == "Time = 0"
    assert image.get_attribute("data-current-frame") == "0"

    page.get_by_title("Forward step").click()

    page.wait_for_function(
        "document.querySelector('#seurat-vcr-time-value').textContent === 'Time = 0.25'"
    )
    assert image.get_attribute("data-current-frame") == "1"
