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


def _drag(page, locator, delta_x=0, delta_y=0, release=True, button="left"):
    bounds = locator.bounding_box()
    assert bounds is not None
    start_x = bounds["x"] + bounds["width"] / 2
    start_y = bounds["y"] + bounds["height"] / 2
    page.mouse.move(start_x, start_y)
    page.mouse.down(button=button)
    page.mouse.move(start_x + delta_x, start_y + delta_y, steps=3)
    if release:
        page.mouse.up(button=button)


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
    page.locator('[data-seurat-resize-runtime="mounted"]').wait_for(
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
            '.seurat-content-column[data-seurat-media-runtime-owner="mounted"]'
        ).count()
        == 1
    )
    assert (
        page.locator(
            '.seurat-content-column[data-seurat-plot-runtime-owner="mounted"]'
        ).count()
        == 1
    )
    assert (
        page.locator(
            '.v-application[data-seurat-interaction-runtime-owner="mounted"]'
        ).count()
        == 1
    )
    assert (
        page.locator('.v-application[data-seurat-resize-runtime-owner="mounted"]').count()
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


def test_floating_panel_drag_moves_and_clamps_panel(page, seurat_server):
    _open_app(page, seurat_server)

    panel = page.locator("#seurat-plot-settings-panel")
    panel.evaluate("panel => { panel.style.display = 'block'; }")
    handle = panel.locator(".seurat-floating-panel-drag-handle")
    initial = panel.bounding_box()
    assert initial is not None

    _drag(page, handle, delta_x=55, delta_y=35)
    moved = panel.bounding_box()
    assert moved["x"] == pytest.approx(initial["x"] + 55, abs=2)
    assert moved["y"] == pytest.approx(initial["y"] + 35, abs=2)
    assert not panel.evaluate("panel => panel.classList.contains('is-dragging')")

    _drag(page, handle, delta_x=-2000, delta_y=-2000)
    clamped = panel.bounding_box()
    assert clamped["x"] == pytest.approx(8, abs=1)
    assert clamped["y"] == pytest.approx(8, abs=1)


def test_floating_panel_runtime_cleans_up_and_owns_window_resize(
    page, seurat_server
):
    _open_app(page, seurat_server)

    root = page.locator(".v-application")
    panel = page.locator("#seurat-plot-settings-panel")
    panel.evaluate("panel => { panel.style.display = 'block'; }")
    handle = panel.locator(".seurat-floating-panel-drag-handle")

    _drag(page, handle, delta_x=20, delta_y=10, release=False)
    assert handle.evaluate("handle => handle.hasPointerCapture(1)")
    assert panel.evaluate("panel => panel.classList.contains('is-dragging')")

    root.evaluate("root => window.seuratInteractionRuntime.unmount(root)")
    assert not handle.evaluate("handle => handle.hasPointerCapture(1)")
    assert not panel.evaluate("panel => panel.classList.contains('is-dragging')")
    page.mouse.up()

    panel.evaluate("panel => { panel.style.left = '2000px'; panel.style.top = '2000px'; }")
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    assert panel.get_attribute("style").find("left: 2000px") >= 0

    root.evaluate("root => window.seuratInteractionRuntime.mount(root)")
    root.evaluate("root => window.seuratInteractionRuntime.mount(root)")
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    clamped = panel.bounding_box()
    assert clamped["x"] + clamped["width"] <= page.viewport_size["width"] - 7
    assert clamped["y"] + clamped["height"] <= page.viewport_size["height"] - 7


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


def test_media_viewport_pan_zoom_and_reset_request(page, seurat_server):
    _open_app(page, seurat_server)

    viewport = page.locator(
        '.seurat-dropcell[data-cell-index="1"] .seurat-panzoom-viewport'
    )
    bounds = viewport.bounding_box()
    assert bounds is not None
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2,
        bounds["y"] + bounds["height"] / 2,
    )
    page.mouse.wheel(0, -120)
    assert viewport.evaluate("viewport => viewport.__seuratPanZoomState.scale") > 1

    viewport.dblclick()
    assert viewport.evaluate(
        "viewport => viewport.__seuratPanZoomState"
    ) == pytest.approx({"scale": 1, "tx": 0, "ty": 0})

    page.keyboard.down("Shift")
    _drag(page, viewport, delta_x=35, delta_y=20)
    page.keyboard.up("Shift")
    panned = viewport.evaluate("viewport => viewport.__seuratPanZoomState")
    assert panned["scale"] == pytest.approx(1)
    assert panned["tx"] == pytest.approx(35, abs=1)
    assert panned["ty"] == pytest.approx(20, abs=1)

    _drag(page, viewport, delta_y=-30, button="middle")
    zoomed = viewport.evaluate("viewport => viewport.__seuratPanZoomState")
    assert zoomed["scale"] > 1

    request = page.locator("#seurat-reset-view-request")
    request.evaluate(
        "element => element.setAttribute('data-reset-view-request', "
        "JSON.stringify({ cell_index: 1, nonce: 1 }))"
    )
    page.wait_for_function(
        "document.querySelector('.seurat-dropcell[data-cell-index=\"1\"] "
        ".seurat-panzoom-viewport').__seuratPanZoomState.scale === 1"
    )
    reset = viewport.evaluate("viewport => viewport.__seuratPanZoomState")
    assert reset == pytest.approx({"scale": 1, "tx": 0, "ty": 0})


def test_media_pan_zoom_lifecycle_cleanup_and_idempotent_remount(
    page, seurat_server
):
    _open_app(page, seurat_server)

    root = page.locator(".seurat-content-column")
    viewport = page.locator(
        '.seurat-dropcell[data-cell-index="1"] .seurat-panzoom-viewport'
    )
    viewport.dblclick()

    page.keyboard.down("Shift")
    _drag(page, viewport, delta_x=20, delta_y=10, release=False)
    assert viewport.evaluate("viewport => viewport.hasPointerCapture(1)")
    assert viewport.evaluate("viewport => viewport.classList.contains('is-panning')")

    root.evaluate("root => window.seuratGridRuntime.unmount(root)")
    assert root.get_attribute("data-seurat-media-runtime-owner") is None
    assert not viewport.evaluate("viewport => viewport.hasPointerCapture(1)")
    assert not viewport.evaluate(
        "viewport => viewport.classList.contains('is-panning')"
    )
    assert not page.locator("body").evaluate(
        "body => body.classList.contains('seurat-panzoom-panning')"
    )
    page.mouse.up()
    page.keyboard.up("Shift")

    before_unmounted_wheel = viewport.evaluate(
        "viewport => ({ ...viewport.__seuratPanZoomState })"
    )
    bounds = viewport.bounding_box()
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2,
        bounds["y"] + bounds["height"] / 2,
    )
    page.mouse.wheel(0, -100)
    assert viewport.evaluate(
        "viewport => viewport.__seuratPanZoomState"
    ) == pytest.approx(before_unmounted_wheel)

    root.evaluate("root => window.seuratGridRuntime.mount(root)")
    root.evaluate("root => window.seuratGridRuntime.mount(root)")
    assert root.get_attribute("data-seurat-media-runtime-owner") == "mounted"
    viewport.dblclick()
    page.mouse.wheel(0, -100)
    assert viewport.evaluate(
        "viewport => viewport.__seuratPanZoomState.scale"
    ) == pytest.approx(1.161834, abs=0.001)


def test_plot_hover_pan_zoom_and_reset_request(page, seurat_server):
    _open_app(page, seurat_server)

    plot = page.locator('.seurat-dropcell[data-cell-index="0"] .seurat-plot1d')
    hover_point = plot.evaluate(
        """plot => {
            const point = plot.__seuratPlotMeta.hoverSeries[0].points[20];
            const rect = plot.getBoundingClientRect();
            return { x: rect.left + point.px, y: rect.top + point.py };
        }"""
    )
    page.keyboard.down("Control")
    page.mouse.move(hover_point["x"], hover_point["y"])
    assert plot.evaluate(
        "plot => plot.__seuratPlotMeta.hoverGroup.getAttribute('display')"
    ) is None
    assert plot.evaluate(
        "plot => plot.__seuratPlotMeta.hoverTip.style.display"
    ) == "block"
    hover_text = plot.evaluate(
        "plot => plot.__seuratPlotMeta.hoverTip.textContent"
    )
    assert "\\n" not in hover_text
    hover_lines = hover_text.splitlines()
    assert len(hover_lines) == 2
    assert hover_lines[0].startswith("x: ")
    assert hover_lines[1].startswith("y: ")
    page.keyboard.up("Control")
    assert plot.evaluate(
        "plot => plot.__seuratPlotMeta.hoverGroup.getAttribute('display')"
    ) == "none"

    initial_axes = plot.evaluate(
        "plot => ({"
        " x: { ...plot.__seuratPlotMeta.xAxis },"
        " y: { ...plot.__seuratPlotMeta.yAxis }"
        "})"
    )
    bounds = plot.bounding_box()
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2,
        bounds["y"] + bounds["height"] / 2,
    )
    page.mouse.wheel(0, -120)
    wheel_state = plot.evaluate("plot => ({ ...plot.__seuratPlotViewState })")
    assert wheel_state["xMax"] - wheel_state["xMin"] < (
        initial_axes["x"]["max"] - initial_axes["x"]["min"]
    )

    plot.dblclick()
    assert plot.evaluate("plot => plot.__seuratPlotViewState") is None

    page.keyboard.down("Shift")
    _drag(page, plot, delta_x=30, delta_y=15)
    page.keyboard.up("Shift")
    pan_state = plot.evaluate("plot => ({ ...plot.__seuratPlotViewState })")
    assert pan_state["xMin"] != pytest.approx(initial_axes["x"]["min"])
    assert pan_state["yMin"] != pytest.approx(initial_axes["y"]["min"])

    _drag(page, plot, delta_y=-25, button="middle")
    middle_zoom_state = plot.evaluate(
        "plot => ({ ...plot.__seuratPlotViewState })"
    )
    assert middle_zoom_state["xMax"] - middle_zoom_state["xMin"] < (
        pan_state["xMax"] - pan_state["xMin"]
    )

    request = page.locator("#seurat-reset-view-request")
    request.evaluate(
        "element => element.setAttribute('data-reset-view-request', "
        "JSON.stringify({ cell_index: 0, nonce: 2 }))"
    )
    page.wait_for_function(
        "document.querySelector('.seurat-dropcell[data-cell-index=\"0\"] "
        ".seurat-plot1d').__seuratPlotViewState === null"
    )


def test_plot_runtime_cleans_up_observers_and_remounts_idempotently(
    page, seurat_server
):
    _open_app(page, seurat_server)

    root = page.locator(".seurat-content-column")
    plot = page.locator('.seurat-dropcell[data-cell-index="0"] .seurat-plot1d')
    plot.dblclick()

    page.keyboard.down("Shift")
    _drag(page, plot, delta_x=20, delta_y=10, release=False)
    assert plot.evaluate("plot => plot.hasPointerCapture(1)")
    assert plot.evaluate("plot => plot.classList.contains('is-panning')")

    root.evaluate("root => window.seuratGridRuntime.unmount(root)")
    assert root.get_attribute("data-seurat-plot-runtime-owner") is None
    assert not plot.evaluate("plot => plot.hasPointerCapture(1)")
    assert not plot.evaluate("plot => plot.classList.contains('is-panning')")
    assert not page.locator("body").evaluate(
        "body => body.classList.contains('seurat-plot-panning')"
    )
    page.mouse.up()
    page.keyboard.up("Shift")

    plot.evaluate("plot => { plot.__seuratPlotRenderKey = 'unmounted'; }")
    page.evaluate("window.seuratGridRuntime.schedulePlotRender()")
    plot.evaluate(
        "plot => plot.setAttribute('data-plot-settings', "
        "JSON.stringify({ background_color: '#ffeeee' }))"
    )
    page.wait_for_timeout(100)
    assert plot.evaluate("plot => plot.__seuratPlotRenderKey") == "unmounted"

    root.evaluate("root => window.seuratGridRuntime.mount(root)")
    root.evaluate("root => window.seuratGridRuntime.mount(root)")
    assert root.get_attribute("data-seurat-plot-runtime-owner") == "mounted"
    page.wait_for_function(
        "document.querySelector('.seurat-plot1d').__seuratPlotRenderKey !== 'unmounted'"
    )
    plot.dblclick()
    initial_span = plot.evaluate(
        "plot => plot.__seuratPlotMeta.xAxis.max - plot.__seuratPlotMeta.xAxis.min"
    )
    bounds = plot.bounding_box()
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2,
        bounds["y"] + bounds["height"] / 2,
    )
    page.mouse.wheel(0, -100)
    zoomed_span = plot.evaluate(
        "plot => plot.__seuratPlotViewState.xMax - plot.__seuratPlotViewState.xMin"
    )
    assert zoomed_span / initial_span == pytest.approx(0.860708, abs=0.002)


def test_variable_panel_resize_supports_keyboard_and_pointer(page, seurat_server):
    _open_app(page, seurat_server)

    panel = page.locator("#seurat-variable-column")
    handle = page.locator("[data-variable-panel-resizer]")
    initial_width = panel.bounding_box()["width"]

    handle.focus()
    handle.press("ArrowRight")
    keyboard_width = panel.bounding_box()["width"]
    assert keyboard_width == pytest.approx(initial_width + 10, abs=1)
    assert float(handle.get_attribute("aria-valuenow")) == pytest.approx(
        keyboard_width, abs=1
    )

    _drag(page, handle, delta_x=40)
    pointer_width = panel.bounding_box()["width"]
    assert pointer_width == pytest.approx(keyboard_width + 40, abs=2)
    assert not page.locator("body").evaluate(
        "body => body.classList.contains('seurat-variable-panel-resizing')"
    )


def test_grid_column_resize_updates_track_state(page, seurat_server):
    _open_app(page, seurat_server)

    grid = page.locator(".seurat-main-grid")
    handle = page.locator(
        '.seurat-dropcell[data-cell-index="0"] '
        '.seurat-grid-col-resize-handle[data-resize-edge="right"]'
    )
    _drag(page, handle, delta_x=45)

    page.wait_for_function(
        "Number(document.querySelector('.seurat-main-grid')"
        ".getAttribute('data-grid-column-sizes').split(',')[0]) > 320"
    )
    sizes = [float(value) for value in grid.get_attribute("data-grid-column-sizes").split(",")]
    assert sizes[0] == pytest.approx(325, abs=2)
    assert sizes[1:] == pytest.approx([280, 280], abs=1)


def test_fit_grid_column_resize_updates_track_weights(page, seurat_server):
    _open_app(page, seurat_server)

    grid = page.locator(".seurat-main-grid")
    grid.evaluate(
        """grid => {
            grid.setAttribute('data-grid-sizing-mode', 'fit');
            grid.setAttribute('data-grid-column-weights', '1,1,1');
            grid.style.gridTemplateColumns = [1, 1, 1]
                .map(() => 'minmax(180px, 1fr)')
                .join(' ');
        }"""
    )
    handle = page.locator(
        '.seurat-dropcell[data-cell-index="0"] '
        '.seurat-grid-col-resize-handle[data-resize-edge="right"]'
    )
    _drag(page, handle, delta_x=30)

    page.wait_for_function(
        "Number(document.querySelector('.seurat-main-grid')"
        ".getAttribute('data-grid-column-weights').split(',')[0]) > 1"
    )
    weights = [
        float(value)
        for value in grid.get_attribute("data-grid-column-weights").split(",")
    ]
    assert weights[0] > 1
    assert weights[1] < 1
    assert weights[0] + weights[1] == pytest.approx(2, abs=0.001)
    assert weights[2] == pytest.approx(1)


def test_grid_row_resize_updates_track_state(page, seurat_server):
    _open_app(page, seurat_server)

    grid = page.locator(".seurat-main-grid")
    handle = page.locator(
        '.seurat-dropcell[data-cell-index="0"] '
        '.seurat-grid-row-resize-handle[data-resize-edge="bottom"]'
    )
    _drag(page, handle, delta_y=35)

    page.wait_for_function(
        "Number(document.querySelector('.seurat-main-grid')"
        ".getAttribute('data-grid-row-sizes').split(',')[0]) > 380"
    )
    sizes = [float(value) for value in grid.get_attribute("data-grid-row-sizes").split(",")]
    assert sizes == pytest.approx([387], abs=2)


def test_grid_corner_resize_updates_both_track_axes(page, seurat_server):
    _open_app(page, seurat_server)

    grid = page.locator(".seurat-main-grid")
    handle = page.locator(
        '.seurat-dropcell[data-cell-index="0"] .seurat-grid-corner-bottom-right'
    )
    _drag(page, handle, delta_x=30, delta_y=25)

    page.wait_for_function(
        "(() => { const grid = document.querySelector('.seurat-main-grid');"
        " return Number(grid.getAttribute('data-grid-column-sizes').split(',')[0]) > 300"
        " && Number(grid.getAttribute('data-grid-row-sizes').split(',')[0]) > 370; })()"
    )
    column_sizes = [
        float(value)
        for value in grid.get_attribute("data-grid-column-sizes").split(",")
    ]
    row_sizes = [float(value) for value in grid.get_attribute("data-grid-row-sizes").split(",")]
    assert column_sizes[0] == pytest.approx(310, abs=2)
    assert row_sizes[0] == pytest.approx(377, abs=2)


def test_resize_runtime_cleans_up_and_mount_is_idempotent(page, seurat_server):
    _open_app(page, seurat_server)

    root = page.locator(".v-application")
    grid = page.locator(".seurat-main-grid")
    variable_handle = page.locator("[data-variable-panel-resizer]")

    _drag(page, variable_handle, delta_x=25, release=False)
    assert page.locator("body").evaluate(
        "body => body.classList.contains('seurat-variable-panel-resizing')"
    )
    assert variable_handle.evaluate(
        "handle => handle.hasPointerCapture(1)"
    )
    root.evaluate("root => window.seuratResizeRuntime.unmount(root)")
    assert root.get_attribute("data-seurat-resize-runtime-owner") is None
    assert not page.locator("body").evaluate(
        "body => body.classList.contains('seurat-variable-panel-resizing')"
    )
    assert not variable_handle.evaluate(
        "handle => handle.classList.contains('seurat-variable-resizer-active')"
    )
    assert not variable_handle.evaluate(
        "handle => handle.hasPointerCapture(1)"
    )
    page.mouse.up()

    panel = page.locator("#seurat-variable-column")
    unmounted_width = panel.bounding_box()["width"]
    variable_handle.focus()
    variable_handle.press("ArrowRight")
    assert panel.bounding_box()["width"] == pytest.approx(unmounted_width, abs=1)

    root.evaluate("root => window.seuratResizeRuntime.mount(root)")
    root.evaluate("root => window.seuratResizeRuntime.mount(root)")
    assert root.get_attribute("data-seurat-resize-runtime-owner") == "mounted"
    page.evaluate(
        """() => {
            const originalTrigger = window.trame.trigger.bind(window.trame);
            window.__seuratResizeTriggerCounts = {};
            window.__seuratResizeRenderCount = 0;
            const originalRender = window.seuratGridRuntime.schedulePlotRender;
            window.seuratGridRuntime.schedulePlotRender = (...args) => {
                window.__seuratResizeRenderCount += 1;
                return originalRender(...args);
            };
            window.trame.trigger = (name, args) => {
                const counts = window.__seuratResizeTriggerCounts;
                counts[name] = (counts[name] || 0) + 1;
                return originalTrigger(name, args);
            };
        }"""
    )
    grid_handle = page.locator(
        '.seurat-dropcell[data-cell-index="0"] '
        '.seurat-grid-col-resize-handle[data-resize-edge="right"]'
    )
    _drag(page, grid_handle, delta_x=20)
    assert page.evaluate(
        "window.__seuratResizeTriggerCounts.set_grid_track_sizes_trigger"
    ) == 1
    assert not grid.evaluate("grid => grid.classList.contains('is-resizing')")
    assert not page.locator("body").evaluate(
        "body => body.classList.contains('seurat-grid-col-resizing')"
    )
    root.evaluate("root => window.seuratResizeRuntime.unmount(root)")
    render_count_after_unmount = page.evaluate("window.__seuratResizeRenderCount")
    page.wait_for_timeout(250)
    assert page.evaluate("window.__seuratResizeRenderCount") == render_count_after_unmount


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
