from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import client, html
from trame.widgets import vuetify3 as vuetify

from db import SCALAR_FIELD_COLORMAP_OPTIONS


def _build_grid_size_picker(ctrl):
    with html.Div(classes="catnip-toolbar-menu", style="margin-top:10px; width:100%;"):
        with html.Button(
            classes="catnip-grid-size-trigger",
            raw_attrs=['type="button"'],
            title="Grid size",
        ):
            html.Span("Grid size", classes="catnip-grid-size-trigger-label")
            html.Span("{{ gridRows + ' x ' + gridCols + ' ▾' }}", classes="catnip-grid-size-trigger-value")
        with vuetify.VMenu(
            activator="parent",
            location="bottom start",
            close_on_content_click=False,
        ):
            with vuetify.VCard(classes="catnip-grid-size-popover", elevation=4):
                with vuetify.VCardText(class_="pa-2"):
                    html.Div("Grid size", classes="catnip-toolbar-popover-title")
                    with html.Div(classes="catnip-grid-picker"):
                        for picker_row in range(1, 9):
                            for picker_col in range(1, 9):
                                html.Button(
                                    "",
                                    classes="catnip-grid-picker-cell",
                                    click=(ctrl.set_grid_layout_size, f"[{picker_row}, {picker_col}]"),
                                    raw_attrs=[
                                        'type="button"',
                                        f'title="{picker_row} x {picker_col}"',
                                        f':class="{{ selected: gridRows >= {picker_row} && gridCols >= {picker_col}, current: gridRows === {picker_row} && gridCols === {picker_col} }}"',
                                    ],
                                )
                    html.Div(
                        "{{ gridRows + ' x ' + gridCols }}",
                        class_="text-caption catnip-grid-picker-label",
                    )
                    with html.Div(classes="catnip-grid-layout-stepper"):
                        html.Span("Rows", class_="text-caption catnip-grid-layout-stepper-label")
                        html.Button(
                            "-",
                            classes="catnip-grid-layout-btn",
                            click=ctrl.delete_grid_row,
                            raw_attrs=['type="button"', ':disabled="gridRows <= gridMinRows"'],
                            title="Delete active row or last row",
                        )
                        html.Span("{{ gridRows }}", class_="text-caption text-center")
                        html.Button(
                            "+",
                            classes="catnip-grid-layout-btn",
                            click=ctrl.add_grid_row,
                            raw_attrs=['type="button"', ':disabled="gridRows >= gridMaxRows"'],
                            title="Add row",
                        )
                    with html.Div(classes="catnip-grid-layout-stepper"):
                        html.Span("Cols", class_="text-caption catnip-grid-layout-stepper-label")
                        html.Button(
                            "-",
                            classes="catnip-grid-layout-btn",
                            click=ctrl.delete_grid_column,
                            raw_attrs=['type="button"', ':disabled="gridCols <= gridMinCols"'],
                            title="Delete active column or last column",
                        )
                        html.Span("{{ gridCols }}", class_="text-caption text-center")
                        html.Button(
                            "+",
                            classes="catnip-grid-layout-btn",
                            click=ctrl.add_grid_column,
                            raw_attrs=['type="button"', ':disabled="gridCols >= gridMaxCols"'],
                            title="Add column",
                        )


def _build_grid_settings_popover(ctrl):
    html.Div("Settings", classes="catnip-toolbar-popover-title")
    with html.Div(classes="catnip-settings-section"):
        html.Div("Layout", classes="catnip-settings-section-title")
        html.Div("Cell layout", classes="catnip-grid-sizing-section-label")
        with html.Div(classes="catnip-grid-sizing-mode"):
            html.Button(
                "Uniform",
                classes="catnip-grid-sizing-mode-btn",
                click=(ctrl.set_grid_layout_mode, "['uniform']"),
                raw_attrs=[
                    'type="button"',
                    ':class="{ active: gridLayoutMode !== \'spanning\' }"',
                ],
                title="Use one cell per grid slot",
            )
            html.Button(
                "Spanning",
                classes="catnip-grid-sizing-mode-btn",
                click=(ctrl.set_grid_layout_mode, "['spanning']"),
                raw_attrs=[
                    'type="button"',
                    ':class="{ active: gridLayoutMode === \'spanning\' }"',
                ],
                title="Allow cells to span multiple rows or columns",
            )
        html.Div("Size mode", classes="catnip-grid-sizing-section-label")
        with html.Div(classes="catnip-grid-sizing-mode"):
            html.Button(
                "Static",
                classes="catnip-grid-sizing-mode-btn",
                click=(ctrl.set_grid_sizing_mode, "['static']"),
                raw_attrs=[
                    'type="button"',
                    ':class="{ active: gridSizingMode !== \'fit\' }"',
                ],
                title="Use fixed-size cells",
            )
            html.Button(
                "Fit window",
                classes="catnip-grid-sizing-mode-btn",
                click=(ctrl.set_grid_sizing_mode, "['fit']"),
                raw_attrs=[
                    'type="button"',
                    ':class="{ active: gridSizingMode === \'fit\' }"',
                ],
                title="Resize cells to fill the grid viewport",
            )
        with vuetify.Template(v_if="gridSizingMode !== 'fit'"):
            html.Div("Cell size", classes="catnip-grid-sizing-section-label")
            with html.Div(classes="catnip-size-stepper"):
                html.Button(
                    "-",
                    classes="catnip-grid-layout-btn",
                    click=(ctrl.set_grid_cell_size, "[Number(gridCellSize || 300) - 10]"),
                    raw_attrs=['type="button"'],
                    title="Decrease cell size",
                )
                html.Input(
                    v_model=("gridCellSize",),
                    classes="catnip-size-stepper-input",
                    change=(ctrl.set_grid_cell_size, "[$event.target.value]"),
                    raw_attrs=[
                        'type="number"',
                        ':min="gridMinCellSize"',
                        ':max="gridMaxCellSize"',
                        'step="10"',
                        'aria-label="Cell size"',
                    ],
                )
                html.Button(
                    "+",
                    classes="catnip-grid-layout-btn",
                    click=(ctrl.set_grid_cell_size, "[Number(gridCellSize || 300) + 10]"),
                    raw_attrs=['type="button"'],
                    title="Increase cell size",
                )
                html.Span("px", classes="catnip-size-stepper-unit")
            html.Button(
                "Reset track sizes",
                classes="catnip-grid-reset-tracks-btn",
                click=ctrl.reset_grid_track_sizes,
                raw_attrs=['type="button"'],
                title="Reset all rows and columns to the current cell size",
            )
        with vuetify.Template(v_if="gridSizingMode === 'fit'"):
            html.Div("Minimum cell size", classes="catnip-grid-sizing-section-label")
            with html.Div(classes="catnip-size-stepper"):
                html.Button(
                    "-",
                    classes="catnip-grid-layout-btn",
                    click=(ctrl.set_grid_fit_min_cell_size, "[Number(gridFitMinCellSize || 180) - 10]"),
                    raw_attrs=['type="button"'],
                    title="Decrease minimum cell size",
                )
                html.Input(
                    v_model=("gridFitMinCellSize",),
                    classes="catnip-size-stepper-input",
                    change=(ctrl.set_grid_fit_min_cell_size, "[$event.target.value]"),
                    raw_attrs=[
                        'type="number"',
                        ':min="gridMinCellSize"',
                        ':max="gridMaxFitMinCellSize"',
                        'step="10"',
                        'aria-label="Minimum cell size"',
                    ],
                )
                html.Button(
                    "+",
                    classes="catnip-grid-layout-btn",
                    click=(ctrl.set_grid_fit_min_cell_size, "[Number(gridFitMinCellSize || 180) + 10]"),
                    raw_attrs=['type="button"'],
                    title="Increase minimum cell size",
                )
                html.Span("px", classes="catnip-size-stepper-unit")
        _build_grid_size_picker(ctrl)
    with html.Div(classes="catnip-settings-section"):
        html.Div("Scalar plots", classes="catnip-settings-section-title")
        with html.Div(classes="catnip-settings-row"):
            html.Span("Create curves", class_="text-caption")
            with html.Select(
                v_model=("scalarPlotPolicy",),
                classes="catnip-scalar-plot-policy",
                title="Generated scalar plot behavior",
            ):
                html.Option("Ask", value="ask")
                html.Option("Generate", value="always")
                html.Option("Never", value="never")


def _build_grid_layout_controls(ctrl):
    with html.Div(classes="catnip-grid-layout-controls"):
        with html.Div(classes="catnip-toolbar-menu"):
            html.Button(
                "⚙",
                classes="catnip-toolbar-menu-btn catnip-toolbar-icon-btn",
                raw_attrs=[
                    'type="button"',
                    'aria-label="Settings"',
                ],
                title="Settings",
            )
            with vuetify.VMenu(
                activator="parent",
                location="bottom end",
                close_on_content_click=False,
            ):
                with vuetify.VCard(classes="catnip-settings-popover", elevation=4):
                    with vuetify.VCardText(class_="pa-2"):
                        _build_grid_settings_popover(ctrl)


def build_ui(server, refresh_variable_list, campaign_name: str = ""):
    state, ctrl = server.state, server.controller
    drag_drop_js = """
    (function initCatnipDragDrop() {
      try {
        if (typeof window.trame === "undefined") {
          setTimeout(initCatnipDragDrop, 200);
          return;
        }
        function inferFpsForVideos(videos) {
          const DEFAULT_FPS = 2.0;
          for (const v of (videos || [])) {
            const fpsAttr = Number(v && v.getAttribute && v.getAttribute("data-fps"));
            if (Number.isFinite(fpsAttr) && fpsAttr > 0) {
              return fpsAttr;
            }
          }
          return DEFAULT_FPS;
        }

        function getVideoFrameCount(video) {
          const count = Number(video && video.getAttribute && video.getAttribute("data-frame-count"));
          return Number.isFinite(count) && count > 0 ? Math.floor(count) : null;
        }

        function getCommonVideoFrameCount(videos) {
          let count = Infinity;
          for (const v of (videos || [])) {
            const frameCount = getVideoFrameCount(v);
            if (frameCount !== null) {
              count = Math.min(count, frameCount);
            }
          }
          return Number.isFinite(count) ? count : null;
        }

        function parseVideoFrameIndices(video) {
          const raw = String(video && video.getAttribute && video.getAttribute("data-frame-indices") || "");
          if (!raw) return [];
          const values = [];
          for (const part of raw.split(",")) {
            const value = Number(part);
            if (Number.isFinite(value)) values.push(value);
          }
          return values;
        }

        function frameOrdinalFromTime(rawSeconds, videos) {
          const fps = inferFpsForVideos(videos);
          const count = getCommonVideoFrameCount(videos);
          const rawOrdinal = Math.round(Math.max(0, Number(rawSeconds) || 0) * fps);
          if (count !== null) {
            return Math.max(0, Math.min(rawOrdinal, Math.max(0, count - 1)));
          }
          return Math.max(0, rawOrdinal);
        }

        function timeForFrameOrdinal(rawOrdinal, videos) {
          const fps = inferFpsForVideos(videos);
          const count = getCommonVideoFrameCount(videos);
          let ordinal = Math.round(Number(rawOrdinal) || 0);
          if (count !== null) {
            ordinal = Math.max(0, Math.min(ordinal, Math.max(0, count - 1)));
          } else {
            ordinal = Math.max(0, ordinal);
          }
          return ordinal / fps;
        }

        function videoFrameLabel(rawOrdinal, videos) {
          const ordinal = Math.max(0, Math.round(Number(rawOrdinal) || 0));
          const firstVideo = (videos || [])[0];
          const indices = parseVideoFrameIndices(firstVideo);
          if (ordinal < indices.length) {
            const value = indices[ordinal];
            return Number.isInteger(value) ? String(value) : String(value);
          }
          return String(ordinal);
        }

        function getGridImageSequencesSafe() {
          if (typeof getGridImageSequences === "function") {
            return getGridImageSequences();
          }
          return Array.from(document.querySelectorAll('img[data-grid-image-sequence="1"]'));
        }

        function parseImageSequenceSources(el) {
          const raw = String(el && el.getAttribute && el.getAttribute("data-frame-sources") || "[]");
          try {
            const sources = JSON.parse(raw);
            return Array.isArray(sources) ? sources.filter(function(src) { return !!src; }) : [];
          } catch (_err) {
            return [];
          }
        }

        function parseImageSequenceFrameIndices(el) {
          const raw = String(el && el.getAttribute && el.getAttribute("data-frame-indices") || "");
          if (!raw) return [];
          const values = [];
          for (const part of raw.split(",")) {
            const value = Number(part);
            if (Number.isFinite(value)) values.push(value);
          }
          return values;
        }

        function parseImageSequenceTimeValues(el) {
          const raw = String(el && el.getAttribute && el.getAttribute("data-time-values") || "");
          if (!raw) return [];
          const values = [];
          for (const part of raw.split(",")) {
            const value = Number(part);
            if (Number.isFinite(value)) values.push(value);
          }
          return values;
        }

        function imageSequencesHavePhysicalTime(sequences) {
          for (const el of (sequences || [])) {
            if (parseImageSequenceTimeValues(el).length) return true;
          }
          return false;
        }

        function isVisibleGridCell(cell) {
          if (!cell) return false;
          try {
            const style = window.getComputedStyle(cell);
            if (style && style.display === "none") return false;
          } catch (_err) {
            // Keep going; visibility is best-effort here.
          }
          return true;
        }

        function collectPlotTimeValues(plots) {
          const values = [];
          if (typeof parsePlotData !== "function") return values;
          for (const el of (plots || [])) {
            const plot = parsePlotData(el);
            const xLabel = String(plot.x_label || "").trim().toLowerCase();
            if (xLabel && xLabel !== "time" && xLabel !== "physical time") continue;
            if (!xLabel) continue;
            const series = Array.isArray(plot.series) ? plot.series : [];
            for (const item of series) {
              const xs = Array.isArray(item && item.x) ? item.x : [];
              for (const raw of xs) {
                const value = Number(raw);
                if (Number.isFinite(value)) values.push(value);
              }
            }
          }
          return values;
        }

        function uniqueSortedTimelineValues(values) {
          const sorted = (values || [])
            .map(function(value) { return Number(value); })
            .filter(function(value) { return Number.isFinite(value); })
            .sort(function(a, b) { return a - b; });
          const result = [];
          for (const value of sorted) {
            if (!result.length) {
              result.push(value);
              continue;
            }
            const previous = result[result.length - 1];
            const tolerance = Math.max(1e-12, 1e-9 * Math.max(1, Math.abs(previous), Math.abs(value)));
            if (Math.abs(value - previous) > tolerance) result.push(value);
          }
          return result;
        }

        function timelineForGridCell(cell) {
          if (!cell || !isVisibleGridCell(cell)) {
            return { values: [], hasPlot: false, hasSequence: false };
          }

          const plots = Array.from(cell.querySelectorAll ? cell.querySelectorAll(".catnip-plot1d") : []);
          const sequences = Array.from(cell.querySelectorAll ? cell.querySelectorAll('img[data-grid-image-sequence="1"]') : []);
          const values = [];
          const plotValues = collectPlotTimeValues(plots);
          values.push.apply(values, plotValues);

          let sequenceValueCount = 0;
          for (const el of sequences) {
            const times = parseImageSequenceTimeValues(el);
            if (times.length) {
              sequenceValueCount += times.length;
              values.push.apply(values, times);
            }
          }

          return {
            values: uniqueSortedTimelineValues(values),
            hasPlot: plotValues.length > 0,
            hasSequence: sequenceValueCount > 0,
          };
        }

        function selectedTimelineDriverCell() {
          const cell = document.querySelector('.catnip-dropcell[data-timeline-driver="1"]');
          return cell && isVisibleGridCell(cell) ? cell : null;
        }

        function autoTimelineDriver() {
          const cells = Array.from(document.querySelectorAll(".catnip-dropcell"));
          let best = null;
          for (const cell of cells) {
            const timeline = timelineForGridCell(cell);
            if (!timeline.values.length) continue;
            const rawIndex = Number(cell.getAttribute("data-cell-index"));
            const index = Number.isFinite(rawIndex) ? rawIndex : cells.indexOf(cell);
            const candidate = {
              cell,
              values: timeline.values,
              hasPlot: timeline.hasPlot,
              index,
            };
            if (
              !best
              || candidate.values.length > best.values.length
              || (
                candidate.values.length === best.values.length
                && candidate.hasPlot
                && !best.hasPlot
              )
              || (
                candidate.values.length === best.values.length
                && candidate.hasPlot === best.hasPlot
                && candidate.index < best.index
              )
            ) {
              best = candidate;
            }
          }
          return best || { values: [] };
        }

        function getPhysicalTimeline(sequences, plots) {
          const selected = selectedTimelineDriverCell();
          if (selected) {
            const selectedTimeline = timelineForGridCell(selected);
            if (selectedTimeline.values.length) return selectedTimeline.values;
          }

          const auto = autoTimelineDriver();
          if (auto.values.length) return auto.values;

          sequences = sequences || getGridImageSequencesSafe();
          plots = plots || (typeof getGridPlots === "function" ? getGridPlots() : []);
          if (sequences.length && !imageSequencesHavePhysicalTime(sequences)) return [];

          const values = [];
          for (const el of (sequences || [])) {
            values.push.apply(values, parseImageSequenceTimeValues(el));
          }
          values.push.apply(values, collectPlotTimeValues(plots));
          return uniqueSortedTimelineValues(values);
        }

        function timelineIndexAtOrBefore(rawTime, timeline) {
          const values = timeline || [];
          if (!values.length) return 0;
          const t = Number(rawTime);
          if (!Number.isFinite(t) || t <= values[0]) return 0;
          if (t >= values[values.length - 1]) return values.length - 1;

          let lo = 0;
          let hi = values.length;
          while (lo < hi) {
            const mid = Math.floor((lo + hi) / 2);
            if (values[mid] <= t) lo = mid + 1;
            else hi = mid;
          }
          return Math.max(0, Math.min(lo - 1, values.length - 1));
        }

        function timelineIndexNearest(rawTime, timeline) {
          const values = timeline || [];
          if (!values.length) return 0;
          const lower = timelineIndexAtOrBefore(rawTime, values);
          const upper = Math.min(lower + 1, values.length - 1);
          const t = Number(rawTime);
          if (!Number.isFinite(t)) return lower;
          return Math.abs(values[upper] - t) < Math.abs(t - values[lower]) ? upper : lower;
        }

        function timeForTimelineIndex(rawIndex, timeline) {
          const values = timeline || [];
          if (!values.length) return 0;
          let index = Math.round(Number(rawIndex) || 0);
          index = Math.max(0, Math.min(index, values.length - 1));
          return values[index];
        }

        function imageSequenceFrameForTime(el, rawTime) {
          const sources = parseImageSequenceSources(el);
          if (!sources.length) return 0;

          const times = parseImageSequenceTimeValues(el);
          if (!times.length) {
            return Math.max(0, Math.min(Math.round(Number(rawTime) || 0), sources.length - 1));
          }

          const index = timelineIndexAtOrBefore(rawTime, times);
          return Math.max(0, Math.min(index, sources.length - 1));
        }

        function formatTimelineValue(value) {
          const number = Number(value);
          if (!Number.isFinite(number)) return String(value);
          if (Number.isInteger(number)) return String(number);
          const absValue = Math.abs(number);
          if (absValue > 0 && (absValue < 1e-3 || absValue >= 1e6)) {
            return number.toExponential(6).replace(/0+e/, "e");
          }
          return String(Number(number.toPrecision(7)));
        }

        function getImageSequenceFrameCount(el) {
          const count = Number(el && el.getAttribute && el.getAttribute("data-frame-count"));
          if (Number.isFinite(count) && count > 0) return Math.floor(count);
          return parseImageSequenceSources(el).length || null;
        }

        function getCommonImageSequenceFrameCount(sequences) {
          let count = Infinity;
          for (const el of (sequences || [])) {
            const frameCount = getImageSequenceFrameCount(el);
            if (frameCount !== null) count = Math.min(count, frameCount);
          }
          return Number.isFinite(count) ? count : null;
        }

        function clampImageSequenceFrame(rawOrdinal, sequences) {
          const count = getCommonImageSequenceFrameCount(sequences);
          let ordinal = Math.round(Number(rawOrdinal) || 0);
          ordinal = Math.max(0, ordinal);
          if (count !== null) ordinal = Math.min(ordinal, Math.max(0, count - 1));
          return ordinal;
        }

        function imageSequenceFrameLabel(rawOrdinal, sequences) {
          const ordinal = clampImageSequenceFrame(rawOrdinal, sequences);
          const firstSequence = (sequences || [])[0];
          const timeValues = parseImageSequenceTimeValues(firstSequence);
          if (ordinal < timeValues.length) {
            return formatTimelineValue(timeValues[ordinal]);
          }
          const indices = parseImageSequenceFrameIndices(firstSequence);
          if (ordinal < indices.length) {
            const value = indices[ordinal];
            return formatTimelineValue(value);
          }
          return String(ordinal);
        }

        function inferFpsForImageSequences(sequences) {
          const DEFAULT_FPS = 2.0;
          for (const el of (sequences || [])) {
            const fpsAttr = Number(el && el.getAttribute && el.getAttribute("data-fps"));
            if (Number.isFinite(fpsAttr) && fpsAttr > 0) return fpsAttr;
          }
          return DEFAULT_FPS;
        }

        function setImageSequenceFrame(rawOrdinal, sequences) {
          const ordinal = clampImageSequenceFrame(rawOrdinal, sequences);
          for (const el of (sequences || [])) {
            const sources = parseImageSequenceSources(el);
            if (!sources.length) continue;
            const idx = Math.max(0, Math.min(ordinal, sources.length - 1));
            if (el.getAttribute("src") !== sources[idx]) {
              el.setAttribute("src", sources[idx]);
            }
            el.setAttribute("data-current-frame", String(idx));
          }
          return ordinal;
        }

        function setImageSequencesForTime(rawTime, sequences) {
          const t = Number(rawTime);
          for (const el of (sequences || [])) {
            const sources = parseImageSequenceSources(el);
            if (!sources.length) continue;
            const idx = imageSequenceFrameForTime(el, t);
            if (el.getAttribute("src") !== sources[idx]) {
              el.setAttribute("src", sources[idx]);
            }
            el.setAttribute("data-current-frame", String(idx));
          }
          return Number.isFinite(t) ? t : 0;
        }

        function getReferenceImageSequenceFrame(sequences) {
          for (const el of (sequences || [])) {
            const value = Number(el && el.getAttribute && el.getAttribute("data-current-frame"));
            if (Number.isFinite(value) && value >= 0) return Math.round(value);
          }
          return 0;
        }

        function getReferenceImageSequenceTime(sequences) {
          for (const el of (sequences || [])) {
            const frame = Number(el && el.getAttribute && el.getAttribute("data-current-frame"));
            if (!Number.isFinite(frame) || frame < 0) continue;
            const times = parseImageSequenceTimeValues(el);
            const index = Math.max(0, Math.min(Math.round(frame), Math.max(0, times.length - 1)));
            if (index < times.length) return times[index];
          }
          return getReferenceImageSequenceFrame(sequences);
        }

        function getVcrSliderFrameValue() {
          const slider = document.getElementById("catnip-vcr-step-slider");
          const raw = Number(slider && slider.value);
          if (Number.isFinite(raw) && raw >= 0) {
            return Math.round(raw);
          }
          return 0;
        }

        function getVcrSliderTimeValue(videos, plots) {
          videos = videos || [];
          plots = plots || (typeof getGridPlots === "function" ? getGridPlots() : []);
          const sequences = getGridImageSequencesSafe();
          const timeline = getPhysicalTimeline(sequences, plots);
          if (timeline.length) {
            return timeForTimelineIndex(getVcrSliderFrameValue(), timeline);
          }
          if (sequences.length) {
            return getVcrSliderFrameValue();
          }
          if (videos.length) {
            return timeForFrameOrdinal(getVcrSliderFrameValue(), videos);
          }

          const slider = document.getElementById("catnip-vcr-step-slider");
          const raw = Number(slider && slider.value);
          const max = Math.max(1, Number(slider && slider.max) || 500);
          const bounds = (typeof getMediaTimelineBounds === "function")
            ? getMediaTimelineBounds(videos, plots)
            : { start: 0, end: 0 };
          const start = Number.isFinite(bounds.start) ? bounds.start : 0;
          const end = Number.isFinite(bounds.end) ? bounds.end : start;
          const progress = Math.max(0, Math.min(1, (Number.isFinite(raw) ? raw : 0) / max));
          return start + progress * (end - start);
        }

        function updateVcrTimeLabelFromSeconds(rawSeconds, videos, plots) {
          videos = videos || [];
          plots = plots || (typeof getGridPlots === "function" ? getGridPlots() : []);
          const sequences = getGridImageSequencesSafe();
          const bounds = (typeof getMediaTimelineBounds === "function")
            ? getMediaTimelineBounds(videos, plots)
            : { start: 0, end: 0, usesVideos: !!(videos && videos.length) };
          const label = document.getElementById("catnip-vcr-time-value");
          const seconds = Number(rawSeconds);
          const safeSeconds = (typeof clampTimeForMedia === "function")
            ? clampTimeForMedia(seconds, videos, plots)
            : (Number.isFinite(seconds) && seconds >= 0 ? seconds : 0);
          const fps = inferFpsForVideos(videos);
          const timeline = getPhysicalTimeline(sequences, plots);
          if (label) {
            if (timeline.length) {
              label.textContent = "Time = " + formatTimelineValue(safeSeconds);
            } else if (sequences.length) {
              const ordinal = clampImageSequenceFrame(safeSeconds, sequences);
              label.textContent = "Time = " + imageSequenceFrameLabel(ordinal, sequences);
            } else if (videos && videos.length) {
              const ordinal = frameOrdinalFromTime(safeSeconds, videos);
              label.textContent = "Time = " + videoFrameLabel(ordinal, videos);
            } else {
              label.textContent = "Time = " + safeSeconds.toFixed(6);
            }
          }

          const slider = document.getElementById("catnip-vcr-step-slider");
          if (typeof updatePlotCursors === "function") {
            updatePlotCursors(safeSeconds, videos);
          }
          window.__catnipGridSyncTime = safeSeconds;
          if (!slider) return;

          if (timeline.length) {
            const maxFrames = Math.max(0, timeline.length - 1);
            slider.min = "0";
            slider.max = String(maxFrames);
            slider.step = "1";
            slider.value = String(Math.max(0, Math.min(timelineIndexNearest(safeSeconds, timeline), maxFrames)));
          } else if (sequences.length) {
            const count = getCommonImageSequenceFrameCount(sequences);
            const maxFrames = count !== null ? Math.max(0, count - 1) : 0;
            const frameValue = clampImageSequenceFrame(safeSeconds, sequences);
            slider.min = "0";
            slider.max = String(maxFrames);
            slider.step = "1";
            slider.value = String(Math.max(0, Math.min(frameValue, maxFrames)));
          } else if (videos && videos.length) {
            const count = getCommonVideoFrameCount(videos);
            let maxFrames = count !== null ? Math.max(0, count - 1) : 1;
            if (count === null) {
              let minDuration = Infinity;
              for (const v of (videos || [])) {
                const d = Number(v && v.duration);
                if (Number.isFinite(d) && d > 0) {
                  minDuration = Math.min(minDuration, d);
                }
              }
              if (Number.isFinite(minDuration)) {
                maxFrames = Math.max(1, Math.round(Math.max(0, minDuration - 0.04) * fps));
              }
            }
            slider.min = "0";
            slider.max = String(maxFrames);
            slider.step = "1";

            const frameValue = frameOrdinalFromTime(safeSeconds, videos);
            const clamped = Math.max(0, Math.min(frameValue, maxFrames));
            slider.value = String(clamped);
          } else {
            const maxFrames = 500;
            const start = Number.isFinite(bounds.start) ? bounds.start : 0;
            const end = Number.isFinite(bounds.end) ? bounds.end : start;
            const range = Math.max(1e-12, end - start);
            const progress = Math.max(0, Math.min(1, (safeSeconds - start) / range));
            slider.min = "0";
            slider.max = String(maxFrames);
            slider.step = "1";
            slider.value = String(Math.round(progress * maxFrames));
          }
        }

        // Always expose a VCR handler, even when drag/drop was initialized
        // in an older page session.
        window.catnipGridVcr = function(action) {
          if (typeof window.__catnipMainGridVcr === "function") {
            window.__catnipMainGridVcr(action);
            return;
          }
          const videos = Array.from(document.querySelectorAll('video[data-grid-video="1"]'));
          if (!videos.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }

          function getCommonEndTime(vs) {
            const count = getCommonVideoFrameCount(vs);
            if (count !== null) {
              return timeForFrameOrdinal(Math.max(0, count - 1), vs);
            }
            let minDuration = Infinity;
            for (const v of vs) {
              const d = Number(v && v.duration);
              if (Number.isFinite(d) && d > 0) {
                minDuration = Math.min(minDuration, d);
              }
            }
            if (!Number.isFinite(minDuration)) return null;
            return Math.max(0, minDuration - 0.04);
          }

          function clampTime(raw) {
            let t = Number(raw);
            if (!Number.isFinite(t) || t < 0) t = 0;
            const commonEnd = getCommonEndTime(videos);
            if (commonEnd !== null) t = Math.min(t, commonEnd);
            return t;
          }

          function setAllTime(raw) {
            const t = clampTime(raw);
            for (const v of videos) {
              try {
                v.currentTime = t;
              } catch (_err) {
                // ignore seek errors
              }
            }
            updateVcrTimeLabelFromSeconds(t, videos);
            return t;
          }

          function pauseAll() {
            for (const v of videos) {
              try {
                v.pause();
              } catch (_err) {
                // ignore pause errors
              }
            }
          }

          function playAll() {
            for (const v of videos) {
              try {
                const p = v.play();
                if (p && typeof p.catch === "function") p.catch(function() {});
              } catch (_err) {
                // ignore autoplay errors
              }
            }
          }

          function inferFrameStepSeconds(vs) {
            const fps = inferFpsForVideos(vs);
            return 1.0 / fps;
          }

          const fps = inferFpsForVideos(videos);
          const frameStep = inferFrameStepSeconds(videos);
          const current = Number(videos[0] && videos[0].currentTime);
          const base = Number.isFinite(current) ? current : 0;
          updateVcrTimeLabelFromSeconds(base, videos);
          const a = String(action || "").trim().toLowerCase();

          if (a === "play") {
            setAllTime(base);
            playAll();
            return;
          }
          if (a === "pause") {
            pauseAll();
            return;
          }
          if (a === "stop") {
            pauseAll();
            setAllTime(0);
            return;
          }
          if (a === "start") {
            setAllTime(0);
            return;
          }
          if (a === "end") {
            const endTime = getCommonEndTime(videos);
            setAllTime(endTime !== null ? endTime : base);
            return;
          }
          if (a === "slider") {
            setAllTime(getVcrSliderTimeValue(videos, []));
            return;
          }
          if (a === "frameback") {
            setAllTime(base - frameStep);
            return;
          }
          if (a === "frame") {
            setAllTime(base + frameStep);
            return;
          }
          if (a === "back") {
            setAllTime(base - frameStep);
            return;
          }
          if (a === "forward") {
            setAllTime(base + frameStep);
          }
        };

        if (!window.__catnipVcrSliderInit) {
          window.__catnipVcrSliderInit = true;
          document.addEventListener("input", function(e) {
            const target = e && e.target;
            if (target && target.id === "catnip-vcr-step-slider") {
              if (window.catnipGridVcr) {
                window.catnipGridVcr("slider");
              }
            }
          }, true);
          document.addEventListener("change", function(e) {
            const target = e && e.target;
            if (target && target.id === "catnip-vcr-step-slider") {
              if (window.catnipGridVcr) {
                window.catnipGridVcr("slider");
              }
            }
          }, true);
        }

        if (!window.__catnipVariablePanelResizeInit) {
          window.__catnipVariablePanelResizeInit = true;
          const MIN_VARIABLE_PANEL_WIDTH = 180;
          const MIN_CONTENT_PANEL_WIDTH = 360;
          let variablePanelResize = null;

          function variablePanelBounds(panel) {
            const row = panel && panel.parentElement;
            const rowWidth = row ? row.getBoundingClientRect().width : window.innerWidth;
            return {
              min: MIN_VARIABLE_PANEL_WIDTH,
              max: Math.max(
                MIN_VARIABLE_PANEL_WIDTH,
                Math.min(rowWidth * 0.5, rowWidth - MIN_CONTENT_PANEL_WIDTH)
              ),
            };
          }

          function setVariablePanelWidth(panel, rawWidth) {
            if (!panel) return;
            const bounds = variablePanelBounds(panel);
            const width = Math.max(bounds.min, Math.min(Number(rawWidth) || bounds.min, bounds.max));
            panel.style.flexBasis = width + "px";
            panel.style.width = width + "px";
            const handle = document.querySelector("[data-variable-panel-resizer]");
            if (handle) {
              handle.setAttribute("aria-valuemin", String(Math.round(bounds.min)));
              handle.setAttribute("aria-valuemax", String(Math.round(bounds.max)));
              handle.setAttribute("aria-valuenow", String(Math.round(width)));
            }
          }

          function finishVariablePanelResize() {
            if (!variablePanelResize) return;
            variablePanelResize.handle.classList.remove("catnip-variable-resizer-active");
            document.body.classList.remove("catnip-variable-panel-resizing");
            variablePanelResize = null;
          }

          document.addEventListener("pointerdown", function(e) {
            const target = e && e.target;
            const handle = target && target.closest
              ? target.closest("[data-variable-panel-resizer]")
              : null;
            if (!handle) return;
            const panel = document.getElementById("catnip-variable-column");
            if (!panel) return;
            e.preventDefault();
            variablePanelResize = {
              handle: handle,
              panel: panel,
              startX: e.clientX,
              startWidth: panel.getBoundingClientRect().width,
            };
            handle.classList.add("catnip-variable-resizer-active");
            document.body.classList.add("catnip-variable-panel-resizing");
          }, true);

          document.addEventListener("pointermove", function(e) {
            if (!variablePanelResize) return;
            e.preventDefault();
            setVariablePanelWidth(
              variablePanelResize.panel,
              variablePanelResize.startWidth + e.clientX - variablePanelResize.startX
            );
          }, true);

          document.addEventListener("pointerup", finishVariablePanelResize, true);
          document.addEventListener("pointercancel", finishVariablePanelResize, true);
          window.addEventListener("blur", finishVariablePanelResize);

          document.addEventListener("keydown", function(e) {
            const target = e && e.target;
            if (!target || !target.matches || !target.matches("[data-variable-panel-resizer]")) return;
            if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
            const panel = document.getElementById("catnip-variable-column");
            if (!panel) return;
            e.preventDefault();
            const step = e.shiftKey ? 40 : 10;
            const direction = e.key === "ArrowLeft" ? -1 : 1;
            setVariablePanelWidth(panel, panel.getBoundingClientRect().width + direction * step);
          }, true);
        }

        if (!window.__catnipFloatingPanelDragInit) {
          window.__catnipFloatingPanelDragInit = true;
          let floatingDrag = null;

          function clampFloatingPanel(panel, left, top) {
            const margin = 8;
            const width = panel.offsetWidth || 560;
            const height = panel.offsetHeight || 360;
            const maxLeft = Math.max(margin, window.innerWidth - width - margin);
            const maxTop = Math.max(margin, window.innerHeight - height - margin);
            return {
              left: Math.max(margin, Math.min(left, maxLeft)),
              top: Math.max(margin, Math.min(top, maxTop)),
            };
          }

          document.addEventListener("pointerdown", function(e) {
            const target = e && e.target;
            const handle = target && target.closest && target.closest(".catnip-floating-panel-drag-handle");
            if (!handle) return;
            const panel = handle.closest(".catnip-floating-options-panel");
            if (!panel) return;
            const rect = panel.getBoundingClientRect();
            floatingDrag = {
              panel,
              startX: Number(e.clientX) || 0,
              startY: Number(e.clientY) || 0,
              left: rect.left,
              top: rect.top,
            };
            panel.classList.add("is-dragging");
            e.preventDefault();
          }, true);

          document.addEventListener("pointermove", function(e) {
            if (!floatingDrag) return;
            const dx = (Number(e.clientX) || 0) - floatingDrag.startX;
            const dy = (Number(e.clientY) || 0) - floatingDrag.startY;
            const pos = clampFloatingPanel(floatingDrag.panel, floatingDrag.left + dx, floatingDrag.top + dy);
            floatingDrag.panel.style.left = pos.left + "px";
            floatingDrag.panel.style.top = pos.top + "px";
          }, true);

          function endFloatingDrag() {
            if (floatingDrag && floatingDrag.panel) {
              floatingDrag.panel.classList.remove("is-dragging");
            }
            floatingDrag = null;
          }

          document.addEventListener("pointerup", endFloatingDrag, true);
          document.addEventListener("pointercancel", endFloatingDrag, true);
          window.addEventListener("resize", function() {
            const panels = document.querySelectorAll(".catnip-floating-options-panel");
            for (const panel of panels) {
              const rect = panel.getBoundingClientRect();
              const pos = clampFloatingPanel(panel, rect.left, rect.top);
              panel.style.left = pos.left + "px";
              panel.style.top = pos.top + "px";
            }
          });
        }

        if (!window.__catnipGridTrackResizeInit) {
          window.__catnipGridTrackResizeInit = true;
          let trackResize = null;

          function parseTrackSizes(raw, count, fallback) {
            const text = String(raw || "").trim();
            const pxParts = Array.from(text.matchAll(/(-?\\d+(?:\\.\\d+)?)px\\b/g))
              .map(function(match) { return Number.parseFloat(match[1]); });
            const parts = pxParts.length >= count
              ? pxParts
              : text.split(/[,\\s]+/).map(function(part) { return Number.parseFloat(part); });
            const sizes = [];
            for (let i = 0; i < count; i += 1) {
              const value = parts[i];
              sizes.push(Number.isFinite(value) && value > 0 ? value : fallback);
            }
            return sizes;
          }

          function clampTrackSize(value, minimum, maximum) {
            const safeMin = Number.isFinite(minimum) ? minimum : 40;
            const safeMax = Number.isFinite(maximum) ? maximum : 10000;
            return Math.max(safeMin, Math.min(safeMax, value));
          }

          function trackTemplate(sizes) {
            return sizes.map(function(size) {
              return String(Math.round(Number(size) || 0)) + "px";
            }).join(" ");
          }

          function fitTrackTemplate(weights, minimum) {
            const safeMin = Number.isFinite(minimum) && minimum > 0 ? minimum : 1;
            return weights.map(function(weight) {
              const safeWeight = Number.isFinite(weight) && weight > 0 ? weight : 1;
              return "minmax(" + String(Math.round(safeMin)) + "px, " + String(Number(safeWeight.toFixed(6))) + "fr)";
            }).join(" ");
          }

          function clearTrackResizeClasses() {
            document.body.classList.remove("catnip-grid-col-resizing");
            document.body.classList.remove("catnip-grid-row-resizing");
            document.body.classList.remove("catnip-grid-corner-resizing");
            document.body.classList.remove("catnip-grid-corner-nwse-resizing");
            document.body.classList.remove("catnip-grid-corner-nesw-resizing");
          }

          function schedulePlotRerenderForTrackResize(delayMs) {
            const run = function() {
              if (typeof scheduleRenderAllPlot1d === "function") {
                scheduleRenderAllPlot1d();
              } else if (typeof window.catnipScheduleRenderAllPlot1d === "function") {
                window.catnipScheduleRenderAllPlot1d();
              }
            };
            const delay = Number(delayMs);
            if (Number.isFinite(delay) && delay > 0) {
              window.setTimeout(run, delay);
            } else if (window.requestAnimationFrame) {
              window.requestAnimationFrame(run);
            } else {
              run();
            }
          }

          function buildTrackResizeAction(grid, axis, edge, index, startX, startY, mode) {
            const isColumn = axis === "column";
            const count = Number(grid.getAttribute(isColumn ? "data-grid-cols" : "data-grid-rows"));
            if (!Number.isInteger(index) || !Number.isInteger(count) || index < 0 || index >= count) return null;

            if (mode === "fit") {
              const neighborIndex = (edge === "left" || edge === "top") ? index - 1 : index + 1;
              if (neighborIndex < 0 || neighborIndex >= count) return null;
              const weights = parseTrackSizes(
                grid.getAttribute(isColumn ? "data-grid-column-weights" : "data-grid-row-weights"),
                count,
                1
              );
              const computed = window.getComputedStyle(grid);
              const renderedSizes = parseTrackSizes(
                isColumn ? computed.gridTemplateColumns : computed.gridTemplateRows,
                count,
                Number(grid.getAttribute(isColumn ? "data-grid-column-fallback" : "data-grid-row-fallback")) || 300
              );
              const rawMinSize = Number(grid.getAttribute(isColumn ? "data-grid-fit-min-column-size" : "data-grid-fit-min-row-size"));
              const minSize = Number.isFinite(rawMinSize) && rawMinSize > 0 ? rawMinSize : 1;
              const currentSize = renderedSizes[index];
              const neighborSize = renderedSizes[neighborIndex];
              const pairSize = currentSize + neighborSize;
              if (!Number.isFinite(pairSize) || pairSize <= (2 * minSize)) return null;
              const pairWeight = weights[index] + weights[neighborIndex];
              return {
                axis,
                mode,
                grid,
                index,
                neighborIndex,
                weights,
                startSize: currentSize,
                pairSize,
                pairWeight: Number.isFinite(pairWeight) && pairWeight > 0 ? pairWeight : 2,
                startX,
                startY,
                direction: (edge === "left" || edge === "top") ? -1 : 1,
                minSize,
              };
            }

            const fallback = Number(grid.getAttribute(isColumn ? "data-grid-column-fallback" : "data-grid-row-fallback"));
            const sizes = parseTrackSizes(
              grid.getAttribute(isColumn ? "data-grid-column-sizes" : "data-grid-row-sizes"),
              count,
              Number.isFinite(fallback) ? fallback : 300
            );
            return {
              axis,
              mode,
              grid,
              index,
              sizes,
              startSize: sizes[index],
              startX,
              startY,
              direction: (edge === "left" || edge === "top") ? -1 : 1,
              minSize: Number(grid.getAttribute(isColumn ? "data-grid-min-column-size" : "data-grid-min-row-size")),
              maxSize: Number(grid.getAttribute(isColumn ? "data-grid-max-column-size" : "data-grid-max-row-size")),
            };
          }

          function beginTrackResize(e, grid, handle, actions) {
            if (!actions || !actions.length) return false;
            trackResize = {
              grid,
              handle,
              actions,
              pointerId: e.pointerId,
            };
            handle.classList.add("active");
            grid.classList.add("is-resizing");
            clearTrackResizeClasses();
            const hasColumn = actions.some(function(action) { return action.axis === "column"; });
            const hasRow = actions.some(function(action) { return action.axis === "row"; });
            if (hasColumn && hasRow) {
              document.body.classList.add("catnip-grid-corner-resizing");
              document.body.classList.add(
                handle.classList.contains("catnip-grid-corner-bottom-left")
                  ? "catnip-grid-corner-nesw-resizing"
                  : "catnip-grid-corner-nwse-resizing"
              );
            } else {
              document.body.classList.add(hasColumn ? "catnip-grid-col-resizing" : "catnip-grid-row-resizing");
            }
            try {
              handle.setPointerCapture(e.pointerId);
            } catch (_) {
              // Pointer capture is best-effort; document-level listeners still handle the drag.
            }
            e.preventDefault();
            e.stopPropagation();
            return true;
          }

          function applyTrackResizeAction(action, e) {
            const delta = action.axis === "column"
              ? ((Number(e.clientX) || 0) - action.startX)
              : ((Number(e.clientY) || 0) - action.startY);
            if (action.mode === "fit") {
              const minSize = Number.isFinite(action.minSize) ? action.minSize : 1;
              const nextSize = clampTrackSize(
                action.startSize + (delta * action.direction),
                minSize,
                action.pairSize - minSize
              );
              const currentWeight = action.pairWeight * (nextSize / action.pairSize);
              action.weights[action.index] = currentWeight;
              action.weights[action.neighborIndex] = action.pairWeight - currentWeight;
              const template = fitTrackTemplate(action.weights, minSize);
              if (action.axis === "column") {
                action.grid.style.gridTemplateColumns = template;
                action.grid.setAttribute("data-grid-column-weights", action.weights.join(","));
              } else {
                action.grid.style.gridTemplateRows = template;
                action.grid.setAttribute("data-grid-row-weights", action.weights.join(","));
              }
              return;
            }

            const nextSize = clampTrackSize(
              action.startSize + (delta * action.direction),
              action.minSize,
              action.maxSize
            );
            action.sizes[action.index] = nextSize;
            const template = trackTemplate(action.sizes);
            if (action.axis === "column") {
              action.grid.style.gridTemplateColumns = template;
              action.grid.setAttribute("data-grid-column-sizes", action.sizes.join(","));
            } else {
              action.grid.style.gridTemplateRows = template;
              action.grid.setAttribute("data-grid-row-sizes", action.sizes.join(","));
            }
          }

          function commitTrackResizeAction(action) {
            if (!window.trame || !window.trame.trigger) return;
            if (action.mode === "fit") {
              window.trame.trigger("set_grid_track_weights_trigger", [action.axis, action.weights.join(",")]);
            } else {
              window.trame.trigger("set_grid_track_sizes_trigger", [action.axis, action.sizes.join(",")]);
            }
          }

          document.addEventListener("pointerdown", function(e) {
            const target = e && e.target;
            const handle = target && target.closest ? target.closest(".catnip-grid-track-resize-handle") : null;
            if (!handle) return;
            if (e.button !== undefined && e.button !== 0) return;
            const grid = handle.closest(".catnip-main-grid");
            if (!grid) return;

            const mode = String(grid.getAttribute("data-grid-sizing-mode") || "static");
            const startX = Number(e.clientX) || 0;
            const startY = Number(e.clientY) || 0;

            if (handle.classList.contains("catnip-grid-corner-resize-handle")) {
              const colEdge = String(handle.getAttribute("data-col-edge") || "right");
              const rowEdge = String(handle.getAttribute("data-row-edge") || "bottom");
              const colIndex = Number(handle.getAttribute("data-col-index"));
              const rowIndex = Number(handle.getAttribute("data-row-index"));
              const actions = [
                buildTrackResizeAction(grid, "column", colEdge, colIndex, startX, startY, mode),
                buildTrackResizeAction(grid, "row", rowEdge, rowIndex, startX, startY, mode),
              ].filter(Boolean);
              if (actions.length === 2) {
                beginTrackResize(e, grid, handle, actions);
              }
              return;
            }

            const isColumn = handle.classList.contains("catnip-grid-col-resize-handle");
            const axis = isColumn ? "column" : "row";
            const edge = String(handle.getAttribute("data-resize-edge") || (isColumn ? "right" : "bottom"));
            const index = Number(handle.getAttribute(isColumn ? "data-col-index" : "data-row-index"));
            const action = buildTrackResizeAction(grid, axis, edge, index, startX, startY, mode);
            if (action) {
              beginTrackResize(e, grid, handle, [action]);
            }
          }, true);

          document.addEventListener("pointermove", function(e) {
            if (!trackResize) return;
            for (const action of (trackResize.actions || [])) {
              applyTrackResizeAction(action, e);
            }
            schedulePlotRerenderForTrackResize();
            e.preventDefault();
            e.stopPropagation();
          }, true);

          function finishTrackResize(e) {
            if (!trackResize) return;
            const current = trackResize;
            if (current.handle) current.handle.classList.remove("active");
            if (current.grid) current.grid.classList.remove("is-resizing");
            clearTrackResizeClasses();
            try {
              if (current.handle && current.pointerId !== undefined) {
                current.handle.releasePointerCapture(current.pointerId);
              }
            } catch (_) {
              // Ignore release failures for pointers that were not captured.
            }
            for (const action of (current.actions || [])) {
              commitTrackResizeAction(action);
            }
            schedulePlotRerenderForTrackResize();
            schedulePlotRerenderForTrackResize(80);
            schedulePlotRerenderForTrackResize(180);
            trackResize = null;
            if (e) {
              e.preventDefault();
              e.stopPropagation();
            }
          }

          document.addEventListener("pointerup", finishTrackResize, true);
          document.addEventListener("pointercancel", finishTrackResize, true);
          document.addEventListener("dragstart", function(e) {
            const target = e && e.target;
            if (target && target.closest && target.closest(".catnip-grid-track-resize-handle")) {
              e.preventDefault();
              e.stopPropagation();
            }
          }, true);
          document.addEventListener("click", function(e) {
            const target = e && e.target;
            if (target && target.closest && target.closest(".catnip-grid-track-resize-handle")) {
              e.preventDefault();
              e.stopPropagation();
            }
          }, true);
        }

        if (!window.__catnipPanZoomInit) {
          window.__catnipPanZoomInit = true;
          let panZoomDrag = null;
          let suppressPanZoomClick = false;
          const PAN_ZOOM_MIN_SCALE = 0.25;
          const PAN_ZOOM_MAX_SCALE = 8;

          function panZoomContent(viewport) {
            if (!viewport || !viewport.children) return null;
            for (const child of viewport.children) {
              if (child.classList && child.classList.contains("catnip-panzoom-content")) {
                return child;
              }
            }
            return viewport.querySelector ? viewport.querySelector(".catnip-panzoom-content") : null;
          }

          function panZoomState(viewport) {
            if (!viewport.__catnipPanZoomState) {
              viewport.__catnipPanZoomState = { scale: 1, tx: 0, ty: 0 };
            }
            return viewport.__catnipPanZoomState;
          }

          function clampPanZoomScale(scale) {
            const value = Number(scale);
            if (!Number.isFinite(value)) return 1;
            return Math.max(PAN_ZOOM_MIN_SCALE, Math.min(PAN_ZOOM_MAX_SCALE, value));
          }

          function applyPanZoom(viewport) {
            const content = panZoomContent(viewport);
            if (!content) return;
            const state = panZoomState(viewport);
            content.style.transform = "translate(" + state.tx.toFixed(2) + "px, " + state.ty.toFixed(2) + "px) scale(" + state.scale.toFixed(6) + ")";
            viewport.classList.toggle(
              "is-panzoomed",
              Math.abs(state.scale - 1) > 1e-6 || Math.abs(state.tx) > 0.5 || Math.abs(state.ty) > 0.5
            );
          }

          function resetPanZoom(viewport) {
            const state = panZoomState(viewport);
            state.scale = 1;
            state.tx = 0;
            state.ty = 0;
            applyPanZoom(viewport);
          }

          function resetPanZoomForCellIndex(cellIndex) {
            const idx = Number(cellIndex);
            if (!Number.isInteger(idx) || idx < 0) return;
            const cell = document.querySelector('.catnip-dropcell[data-cell-index="' + String(idx) + '"]');
            if (!cell) return;
            const viewports = cell.querySelectorAll ? cell.querySelectorAll(".catnip-panzoom-viewport") : [];
            for (const viewport of viewports) {
              resetPanZoom(viewport);
            }
            if (window.catnipResetPlotViewForCellIndex) {
              window.catnipResetPlotViewForCellIndex(idx);
            }
          }

          function setPanZoomScaleAt(viewport, base, clientX, clientY, scale) {
            const rect = viewport.getBoundingClientRect();
            const state = panZoomState(viewport);
            const nextScale = clampPanZoomScale(scale);
            const localX = (Number(clientX) || 0) - rect.left;
            const localY = (Number(clientY) || 0) - rect.top;
            const contentX = (localX - base.tx) / base.scale;
            const contentY = (localY - base.ty) / base.scale;
            state.scale = nextScale;
            state.tx = localX - contentX * nextScale;
            state.ty = localY - contentY * nextScale;
            applyPanZoom(viewport);
          }

          function zoomPanZoomAt(viewport, clientX, clientY, factor) {
            const base = Object.assign({}, panZoomState(viewport));
            setPanZoomScaleAt(viewport, base, clientX, clientY, base.scale * factor);
          }

          function panZoomViewportFromEvent(e) {
            const target = e && e.target;
            const viewport = target && target.closest ? target.closest(".catnip-panzoom-viewport") : null;
            if (!viewport || target.closest(".catnip-grid-track-resize-handle")) return null;
            return viewport;
          }

          document.addEventListener("pointerdown", function(e) {
            const viewport = panZoomViewportFromEvent(e);
            if (!viewport) return;
            const isShiftPan = e.button === 0 && e.shiftKey;
            const isMiddleZoom = e.button === 1;
            if (!isShiftPan && !isMiddleZoom) return;

            const state = Object.assign({}, panZoomState(viewport));
            panZoomDrag = {
              viewport,
              mode: isMiddleZoom ? "zoom" : "pan",
              startX: Number(e.clientX) || 0,
              startY: Number(e.clientY) || 0,
              base: state,
              pointerId: e.pointerId,
              moved: false,
            };
            viewport.classList.add(isMiddleZoom ? "is-zooming" : "is-panning");
            document.body.classList.add(isMiddleZoom ? "catnip-panzoom-zooming" : "catnip-panzoom-panning");
            try {
              viewport.setPointerCapture(e.pointerId);
            } catch (_) {
              // Pointer capture is best-effort; document listeners keep the drag alive.
            }
            e.preventDefault();
            e.stopPropagation();
          }, true);

          document.addEventListener("pointermove", function(e) {
            if (!panZoomDrag) return;
            const dx = (Number(e.clientX) || 0) - panZoomDrag.startX;
            const dy = (Number(e.clientY) || 0) - panZoomDrag.startY;
            if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
              panZoomDrag.moved = true;
            }
            const state = panZoomState(panZoomDrag.viewport);
            if (panZoomDrag.mode === "pan") {
              state.scale = panZoomDrag.base.scale;
              state.tx = panZoomDrag.base.tx + dx;
              state.ty = panZoomDrag.base.ty + dy;
              applyPanZoom(panZoomDrag.viewport);
            } else {
              const factor = Math.exp(-dy * 0.01);
              setPanZoomScaleAt(
                panZoomDrag.viewport,
                panZoomDrag.base,
                panZoomDrag.startX,
                panZoomDrag.startY,
                panZoomDrag.base.scale * factor
              );
            }
            e.preventDefault();
            e.stopPropagation();
          }, true);

          function finishPanZoomDrag(e) {
            if (!panZoomDrag) return;
            const current = panZoomDrag;
            current.viewport.classList.remove("is-panning");
            current.viewport.classList.remove("is-zooming");
            document.body.classList.remove("catnip-panzoom-panning");
            document.body.classList.remove("catnip-panzoom-zooming");
            try {
              if (current.pointerId !== undefined) {
                current.viewport.releasePointerCapture(current.pointerId);
              }
            } catch (_) {
              // Ignore release failures for pointers that were not captured.
            }
            suppressPanZoomClick = !!current.moved;
            panZoomDrag = null;
            if (e) {
              e.preventDefault();
              e.stopPropagation();
            }
          }

          document.addEventListener("pointerup", finishPanZoomDrag, true);
          document.addEventListener("pointercancel", finishPanZoomDrag, true);
          document.addEventListener("wheel", function(e) {
            const viewport = panZoomViewportFromEvent(e);
            if (!viewport) return;
            const factor = Math.exp(-(Number(e.deltaY) || 0) * 0.0015);
            zoomPanZoomAt(viewport, e.clientX, e.clientY, factor);
            e.preventDefault();
            e.stopPropagation();
          }, { capture: true, passive: false });
          document.addEventListener("dblclick", function(e) {
            const viewport = panZoomViewportFromEvent(e);
            if (!viewport) return;
            resetPanZoom(viewport);
            e.preventDefault();
            e.stopPropagation();
          }, true);
          document.addEventListener("dragstart", function(e) {
            const viewport = panZoomViewportFromEvent(e);
            if (viewport && (panZoomDrag || e.shiftKey)) {
              e.preventDefault();
              e.stopPropagation();
            }
          }, true);
          document.addEventListener("auxclick", function(e) {
            const viewport = panZoomViewportFromEvent(e);
            if (viewport && e.button === 1) {
              e.preventDefault();
              e.stopPropagation();
            }
          }, true);
          document.addEventListener("click", function(e) {
            if (!suppressPanZoomClick) return;
            suppressPanZoomClick = false;
            const viewport = panZoomViewportFromEvent(e);
            if (!viewport) return;
            e.preventDefault();
            e.stopPropagation();
          }, true);
          window.catnipResetPanZoomForCellIndex = resetPanZoomForCellIndex;

          let lastResetViewRequest = "";
          function handleResetViewRequest(raw) {
            const text = String(raw || "");
            if (!text || text === lastResetViewRequest) return;
            lastResetViewRequest = text;
            try {
              const request = JSON.parse(text);
              resetPanZoomForCellIndex(request && request.cell_index);
            } catch (_err) {
              // Ignore malformed transient reset requests.
            }
          }
          function scanResetViewRequest() {
            const el = document.getElementById("catnip-reset-view-request");
            if (!el) return;
            handleResetViewRequest(el.getAttribute("data-reset-view-request") || "");
          }
          const resetViewObserver = new MutationObserver(function() {
            scanResetViewRequest();
          });
          resetViewObserver.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["data-reset-view-request"],
          });
          scanResetViewRequest();
        }

        if (window.__catnipDnDInit) return;
        window.__catnipDnDInit = true;
        const gridVcrState = {
          playing: false,
          syncTime: 0,
          timelinePosition: 0,
          syncTimer: null,
          lastTickMs: 0,
        };
        let gridMediaSyncTimer = null;

        setupPlot1dObserver();

        function getGridVideos() {
          return Array.from(document.querySelectorAll('video[data-grid-video="1"]'));
        }

        function getGridImageSequences() {
          return Array.from(document.querySelectorAll('img[data-grid-image-sequence="1"]'));
        }

        function isGridVideo(target) {
          return !!(target && target.matches && target.matches('video[data-grid-video="1"]'));
        }

        function getGridPlots() {
          return Array.from(document.querySelectorAll(".catnip-plot1d"));
        }

        function finiteNumber(value, fallback) {
          const n = Number(value);
          return Number.isFinite(n) ? n : fallback;
        }

        function createSvgNode(name) {
          return document.createElementNS("http://www.w3.org/2000/svg", name);
        }

        function trimPlotNumberText(text) {
          let out = String(text || "");
          if ((out.indexOf("e") >= 0) || (out.indexOf("E") >= 0)) return out;
          while ((out.indexOf(".") >= 0) && out.endsWith("0")) {
            out = out.slice(0, -1);
          }
          if (out.endsWith(".")) out = out.slice(0, -1);
          return out;
        }

        function formatPlotTick(value) {
          const n = Number(value);
          if (!Number.isFinite(n)) return "";
          const abs = Math.abs(n);
          if ((abs >= 10000) || (abs > 0 && abs < 0.001)) return n.toExponential(2);
          const text = n.toPrecision(3);
          return trimPlotNumberText(text);
        }

        function formatPlotHoverValue(value) {
          const n = Number(value);
          if (!Number.isFinite(n)) return "";
          const abs = Math.abs(n);
          const text = ((abs >= 10000) || (abs > 0 && abs < 0.001))
            ? n.toExponential(4)
            : n.toPrecision(6);
          return trimPlotNumberText(text);
        }

        function parsePlotData(el) {
          if (!el) return {};
          const raw = el.getAttribute("data-plot") || "{}";
          if (el.__catnipPlotRaw === raw && el.__catnipPlotData) {
            return el.__catnipPlotData;
          }
          if (el.__catnipPlotRaw !== undefined && el.__catnipPlotRaw !== raw) {
            el.__catnipPlotViewState = null;
            el.__catnipPlotRenderKey = "";
          }
          try {
            el.__catnipPlotData = JSON.parse(raw);
            el.__catnipPlotRaw = raw;
          } catch (_err) {
            el.__catnipPlotData = {};
            el.__catnipPlotRaw = raw;
          }
          return el.__catnipPlotData || {};
        }

        function parsePlotSettings(el) {
          if (!el) return {};
          const raw = el.getAttribute("data-plot-settings") || "{}";
          if (el.__catnipPlotSettingsRaw === raw && el.__catnipPlotSettings) {
            return el.__catnipPlotSettings;
          }
          try {
            el.__catnipPlotSettings = JSON.parse(raw);
            el.__catnipPlotSettingsRaw = raw;
          } catch (_err) {
            el.__catnipPlotSettings = {};
            el.__catnipPlotSettingsRaw = raw;
          }
          return el.__catnipPlotSettings || {};
        }

        function plotSeriesKey(item, index) {
          const sourceKey = String((item && item.source_key) || "").trim();
          if (sourceKey) return sourceKey;
          const sourceLabel = String((item && item.source_label) || "").trim();
          return sourceLabel || ("series:" + index);
        }

        function normalizeLineStyle(value) {
          const style = String(value || "solid").toLowerCase().replace("_", "-");
          return ["solid", "dash", "dot", "dash-dot"].includes(style) ? style : "solid";
        }

        function lineStyleDashArray(value, lineWidth) {
          const style = normalizeLineStyle(value);
          const width = Math.max(0.5, finiteNumber(lineWidth, 2.5));
          if (style === "dash") return String(4 * width) + " " + String(2.5 * width);
          if (style === "dot") return String(0.8 * width) + " " + String(2 * width);
          if (style === "dash-dot") return String(4 * width) + " " + String(2 * width) + " " + String(0.8 * width) + " " + String(2 * width);
          return "";
        }

        function normalizePlotSettings(raw) {
          raw = raw || {};
          const xScale = String(raw.x_scale || "linear").toLowerCase() === "log" ? "log" : "linear";
          const yScale = String(raw.y_scale || "linear").toLowerCase() === "log" ? "log" : "linear";
          const lineWidth = Math.max(0.5, Math.min(8, finiteNumber(raw.line_width, 2.5)));
          return {
            x_auto: raw.x_auto !== false,
            x_min: finiteNumber(raw.x_min, NaN),
            x_max: finiteNumber(raw.x_max, NaN),
            x_scale: xScale,
            y_auto: raw.y_auto !== false,
            y_min: finiteNumber(raw.y_min, NaN),
            y_max: finiteNumber(raw.y_max, NaN),
            y_scale: yScale,
            series_colors: (raw.series_colors && typeof raw.series_colors === "object") ? raw.series_colors : {},
            series_styles: (raw.series_styles && typeof raw.series_styles === "object") ? raw.series_styles : {},
            line_width: lineWidth,
            show_grid: raw.show_grid !== false,
            show_cursor: raw.show_cursor !== false,
            background_color: String(raw.background_color || "#ffffff"),
            grid_color: String(raw.grid_color || "#e8e8e8"),
            cursor_color: String(raw.cursor_color || "#111111"),
          };
        }

        function positivePlotBounds(series, axisName) {
          const field = axisName === "x" ? "x" : "y";
          let minValue = Infinity;
          let maxValue = -Infinity;
          for (const item of (series || [])) {
            const values = Array.isArray(item && item[field]) ? item[field] : [];
            for (const rawValue of values) {
              const value = Number(rawValue);
              if (Number.isFinite(value) && value > 0) {
                minValue = Math.min(minValue, value);
                maxValue = Math.max(maxValue, value);
              }
            }
          }
          if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) return null;
          return { min: minValue, max: maxValue };
        }

        function resolvePlotAxis(plot, series, settings, axisName) {
          const autoKey = axisName + "_auto";
          const minKey = axisName + "_min";
          const maxKey = axisName + "_max";
          const scaleKey = axisName + "_scale";
          const scale = settings[scaleKey] === "log" ? "log" : "linear";
          const autoRange = settings[autoKey] !== false;
          let minValue = autoRange
            ? finiteNumber(plot[minKey], axisName === "x" ? 0 : 0)
            : finiteNumber(settings[minKey], NaN);
          let maxValue = autoRange
            ? finiteNumber(plot[maxKey], axisName === "x" ? 1 : 1)
            : finiteNumber(settings[maxKey], NaN);

          if (scale === "log") {
            const positiveBounds = positivePlotBounds(series, axisName);
            if (autoRange && positiveBounds) {
              const logMin = Math.log10(positiveBounds.min);
              const logMax = Math.log10(positiveBounds.max);
              if (Math.abs(logMax - logMin) <= 1e-12) {
                minValue = Math.pow(10, logMin - 0.5);
                maxValue = Math.pow(10, logMax + 0.5);
              } else {
                const pad = (logMax - logMin) * 0.04;
                minValue = Math.pow(10, logMin - pad);
                maxValue = Math.pow(10, logMax + pad);
              }
            }
            if (!Number.isFinite(minValue) || !Number.isFinite(maxValue) || minValue <= 0 || maxValue <= 0 || minValue >= maxValue) {
              if (positiveBounds) {
                minValue = positiveBounds.min;
                maxValue = positiveBounds.max;
              } else {
                minValue = 1;
                maxValue = 10;
              }
            }
            let tMin = Math.log10(minValue);
            let tMax = Math.log10(maxValue);
            if (Math.abs(tMax - tMin) <= 1e-12) {
              tMin -= 0.5;
              tMax += 0.5;
              minValue = Math.pow(10, tMin);
              maxValue = Math.pow(10, tMax);
            }
            return {
              min: minValue,
              max: maxValue,
              tMin,
              tMax,
              scale,
              transform: function(value) {
                const n = Number(value);
                return Number.isFinite(n) && n > 0 ? Math.log10(n) : NaN;
              },
              inverse: function(value) {
                return Math.pow(10, value);
              },
            };
          }

          if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
            minValue = axisName === "x" ? 0 : 0;
            maxValue = axisName === "x" ? 1 : 1;
          }
          if (Math.abs(maxValue - minValue) <= 1e-12) {
            minValue -= 0.5;
            maxValue += 0.5;
          }
          return {
            min: minValue,
            max: maxValue,
            tMin: minValue,
            tMax: maxValue,
            scale,
            transform: function(value) {
              const n = Number(value);
              return Number.isFinite(n) ? n : NaN;
            },
            inverse: function(value) {
              return value;
            },
          };
        }

        function plotViewRenderKey(el) {
          const state = el && el.__catnipPlotViewState;
          if (!state) return "view:default";
          const values = [
            state.xScale,
            state.yScale,
            state.xMin,
            state.xMax,
            state.yMin,
            state.yMax,
          ];
          return "view:" + values.map(function(value) {
            const n = Number(value);
            return Number.isFinite(n) ? n.toPrecision(16) : String(value || "");
          }).join(",");
        }

        function plotAxisFromRange(axis, minValue, maxValue) {
          if (!axis) return null;
          let min = Number(minValue);
          let max = Number(maxValue);
          if (!Number.isFinite(min) || !Number.isFinite(max) || min >= max) return null;

          if (axis.scale === "log") {
            if (min <= 0 || max <= 0) return null;
            let tMin = Math.log10(min);
            let tMax = Math.log10(max);
            if (!Number.isFinite(tMin) || !Number.isFinite(tMax) || tMin >= tMax) return null;
            if (Math.abs(tMax - tMin) <= 1e-12) {
              const center = (tMin + tMax) * 0.5;
              tMin = center - 0.5;
              tMax = center + 0.5;
              min = Math.pow(10, tMin);
              max = Math.pow(10, tMax);
            }
            return {
              min,
              max,
              tMin,
              tMax,
              scale: "log",
              transform: axis.transform,
              inverse: axis.inverse,
            };
          }

          if (Math.abs(max - min) <= 1e-12) {
            const center = (min + max) * 0.5;
            min = center - 0.5;
            max = center + 0.5;
          }
          return {
            min,
            max,
            tMin: min,
            tMax: max,
            scale: "linear",
            transform: axis.transform,
            inverse: axis.inverse,
          };
        }

        function plotAxisFromTransformRange(axis, tMin, tMax) {
          if (!axis) return null;
          let nextTMin = Number(tMin);
          let nextTMax = Number(tMax);
          if (!Number.isFinite(nextTMin) || !Number.isFinite(nextTMax) || nextTMin >= nextTMax) return null;
          const span = nextTMax - nextTMin;
          if (span <= 1e-12) {
            const center = (nextTMin + nextTMax) * 0.5;
            nextTMin = center - 0.5;
            nextTMax = center + 0.5;
          }
          return plotAxisFromRange(axis, axis.inverse(nextTMin), axis.inverse(nextTMax));
        }

        function plotViewStateForAxes(el, xAxis, yAxis) {
          const state = el && el.__catnipPlotViewState;
          if (!state) return null;
          if (state.xScale !== xAxis.scale || state.yScale !== yAxis.scale) {
            el.__catnipPlotViewState = null;
            return null;
          }
          const viewXAxis = plotAxisFromRange(xAxis, state.xMin, state.xMax);
          const viewYAxis = plotAxisFromRange(yAxis, state.yMin, state.yMax);
          if (!viewXAxis || !viewYAxis) {
            el.__catnipPlotViewState = null;
            return null;
          }
          return { xAxis: viewXAxis, yAxis: viewYAxis };
        }

        function setPlotViewStateFromAxes(el, xAxis, yAxis) {
          if (!el || !xAxis || !yAxis) return;
          el.__catnipPlotViewState = {
            xScale: xAxis.scale,
            yScale: yAxis.scale,
            xMin: xAxis.min,
            xMax: xAxis.max,
            yMin: yAxis.min,
            yMax: yAxis.max,
          };
          el.__catnipPlotRenderKey = "";
        }

        function rerenderPlotView(el) {
          if (!el) return;
          renderPlot1d(el);
          if (typeof updatePlotCursors === "function") {
            updatePlotCursors(window.__catnipGridSyncTime || 0, getGridVideos());
          }
        }

        function resetPlotView(el) {
          if (!el) return;
          el.__catnipPlotViewState = null;
          el.__catnipPlotRenderKey = "";
          renderPlot1d(el);
          if (typeof updatePlotCursors === "function") {
            updatePlotCursors(window.__catnipGridSyncTime || 0, getGridVideos());
          }
        }

        function resetPlotViewForCellIndex(cellIndex) {
          const idx = Number(cellIndex);
          if (!Number.isInteger(idx) || idx < 0) return;
          const cell = document.querySelector('.catnip-dropcell[data-cell-index="' + String(idx) + '"]');
          if (!cell) return;
          const plots = cell.querySelectorAll ? cell.querySelectorAll(".catnip-plot1d") : [];
          for (const el of plots) {
            resetPlotView(el);
          }
        }
        window.catnipResetPlotViewForCellIndex = resetPlotViewForCellIndex;

        function plotLocalPoint(el, event) {
          const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { left: 0, top: 0 };
          return {
            x: (Number(event && event.clientX) || 0) - rect.left,
            y: (Number(event && event.clientY) || 0) - rect.top,
          };
        }

        function clampPlotLocalPoint(meta, point) {
          const left = meta.pad.left;
          const right = meta.pad.left + meta.plotW;
          const top = meta.pad.top;
          const bottom = meta.pad.top + meta.plotH;
          return {
            x: Math.max(left, Math.min(right, Number(point && point.x) || left)),
            y: Math.max(top, Math.min(bottom, Number(point && point.y) || top)),
          };
        }

        function plotAxisTForLocalPoint(axis, meta, point, axisName) {
          const safePoint = clampPlotLocalPoint(meta, point);
          const span = axis.tMax - axis.tMin;
          if (axisName === "y") {
            const fracY = (safePoint.y - meta.pad.top) / Math.max(1, meta.plotH);
            return axis.tMax - fracY * span;
          }
          const fracX = (safePoint.x - meta.pad.left) / Math.max(1, meta.plotW);
          return axis.tMin + fracX * span;
        }

        function zoomPlotAxisAround(axis, centerT, rangeFactor) {
          const factor = Math.max(0.02, Math.min(50, Number(rangeFactor) || 1));
          const nextTMin = centerT - (centerT - axis.tMin) * factor;
          const nextTMax = centerT + (axis.tMax - centerT) * factor;
          return plotAxisFromTransformRange(axis, nextTMin, nextTMax);
        }

        function zoomPlotViewAt(el, event, rangeFactor) {
          if (!el) return;
          renderPlot1d(el);
          const meta = el.__catnipPlotMeta;
          if (!meta || !meta.xAxis || !meta.yAxis) return;
          const point = plotLocalPoint(el, event);
          const centerX = plotAxisTForLocalPoint(meta.xAxis, meta, point, "x");
          const centerY = plotAxisTForLocalPoint(meta.yAxis, meta, point, "y");
          const nextXAxis = zoomPlotAxisAround(meta.xAxis, centerX, rangeFactor);
          const nextYAxis = zoomPlotAxisAround(meta.yAxis, centerY, rangeFactor);
          if (!nextXAxis || !nextYAxis) return;
          setPlotViewStateFromAxes(el, nextXAxis, nextYAxis);
          rerenderPlotView(el);
        }

        function renderPlot1d(el) {
          const plot = parsePlotData(el);
          const settings = normalizePlotSettings(parsePlotSettings(el));
          const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 0, height: 0 };
          const width = Math.max(240, Math.round(rect.width || el.clientWidth || 300));
          const height = Math.max(180, Math.round(rect.height || el.clientHeight || 300));
          const renderKey = String(el.__catnipPlotRaw || "") + "|" + String(el.__catnipPlotSettingsRaw || "") + "|" + width + "x" + height + "|" + plotViewRenderKey(el);
          if (el.__catnipPlotRenderKey === renderKey && el.querySelector("svg")) {
            return;
          }

          el.__catnipPlotRenderKey = renderKey;
          el.innerHTML = "";
          const svg = createSvgNode("svg");
          svg.setAttribute("viewBox", "0 0 " + width + " " + height);
          svg.setAttribute("width", "100%");
          svg.setAttribute("height", "100%");
          svg.setAttribute("preserveAspectRatio", "none");
          svg.style.display = "block";
          svg.style.background = "#ffffff";
          el.appendChild(svg);

          const series = Array.isArray(plot.series) ? plot.series : [];
          if (!series.length) {
            const text = createSvgNode("text");
            text.setAttribute("x", String(width / 2));
            text.setAttribute("y", String(height / 2));
            text.setAttribute("text-anchor", "middle");
            text.setAttribute("font-size", "12");
            text.setAttribute("fill", "#666666");
            text.textContent = "No plot data";
            svg.appendChild(text);
            return;
          }

          const pad = { left: 52, right: 14, top: 12, bottom: 40 };
          const plotW = Math.max(1, width - pad.left - pad.right);
          const plotH = Math.max(1, height - pad.top - pad.bottom);
          let xAxis = resolvePlotAxis(plot, series, settings, "x");
          let yAxis = resolvePlotAxis(plot, series, settings, "y");
          const defaultXAxis = xAxis;
          const defaultYAxis = yAxis;
          const viewAxes = plotViewStateForAxes(el, xAxis, yAxis);
          if (viewAxes) {
            xAxis = viewAxes.xAxis;
            yAxis = viewAxes.yAxis;
          }
          const dataXMin = finiteNumber(plot.data_x_min, xAxis.min);
          const dataXMax = finiteNumber(plot.data_x_max, xAxis.max);

          function sx(value) {
            const tv = xAxis.transform(value);
            if (!Number.isFinite(tv)) return NaN;
            return pad.left + ((tv - xAxis.tMin) / (xAxis.tMax - xAxis.tMin)) * plotW;
          }
          function sy(value) {
            const tv = yAxis.transform(value);
            if (!Number.isFinite(tv)) return NaN;
            return pad.top + plotH - ((tv - yAxis.tMin) / (yAxis.tMax - yAxis.tMin)) * plotH;
          }

          const frame = createSvgNode("rect");
          frame.setAttribute("x", String(pad.left));
          frame.setAttribute("y", String(pad.top));
          frame.setAttribute("width", String(plotW));
          frame.setAttribute("height", String(plotH));
          frame.setAttribute("fill", settings.background_color || "#ffffff");
          frame.setAttribute("stroke", "#3f3f3f");
          frame.setAttribute("stroke-width", "1");
          svg.appendChild(frame);

          for (let i = 0; i < 5; i += 1) {
            const frac = i / 4;
            const gx = pad.left + frac * plotW;
            const gy = pad.top + frac * plotH;
            if (settings.show_grid) {
              const gridV = createSvgNode("line");
              gridV.setAttribute("x1", String(gx));
              gridV.setAttribute("x2", String(gx));
              gridV.setAttribute("y1", String(pad.top));
              gridV.setAttribute("y2", String(pad.top + plotH));
              gridV.setAttribute("stroke", settings.grid_color || "#e8e8e8");
              svg.appendChild(gridV);

              const gridH = createSvgNode("line");
              gridH.setAttribute("x1", String(pad.left));
              gridH.setAttribute("x2", String(pad.left + plotW));
              gridH.setAttribute("y1", String(gy));
              gridH.setAttribute("y2", String(gy));
              gridH.setAttribute("stroke", settings.grid_color || "#e8e8e8");
              svg.appendChild(gridH);
            }

            const xTick = createSvgNode("text");
            xTick.setAttribute("x", String(gx));
            xTick.setAttribute("y", String(pad.top + plotH + 20));
            xTick.setAttribute("text-anchor", "middle");
            xTick.setAttribute("font-size", "12");
            xTick.setAttribute("fill", "#333333");
            xTick.textContent = formatPlotTick(xAxis.inverse(xAxis.tMin + frac * (xAxis.tMax - xAxis.tMin)));
            svg.appendChild(xTick);

            const yTick = createSvgNode("text");
            yTick.setAttribute("x", String(pad.left - 8));
            yTick.setAttribute("y", String(gy + 4));
            yTick.setAttribute("text-anchor", "end");
            yTick.setAttribute("font-size", "12");
            yTick.setAttribute("fill", "#333333");
            yTick.textContent = formatPlotTick(yAxis.inverse(yAxis.tMax - frac * (yAxis.tMax - yAxis.tMin)));
            svg.appendChild(yTick);
          }

          const hoverSeries = [];
          for (let i = 0; i < series.length; i += 1) {
            const item = series[i] || {};
            const xs = Array.isArray(item.x) ? item.x : [];
            const ys = Array.isArray(item.y) ? item.y : [];
            const n = Math.min(xs.length, ys.length);
            let d = "";
            let moveNext = true;
            const seriesKey = plotSeriesKey(item, i);
            const seriesStyle = (settings.series_styles && settings.series_styles[seriesKey]) || {};
            const lineStyle = normalizeLineStyle(seriesStyle.line_style || "solid");
            const color = String(seriesStyle.color || settings.series_colors[seriesKey] || item.color || "#1565c0");
            const sourceLabel = String(item.source_label || item.source_key || ("Series " + (i + 1))).trim();
            const points = [];
            for (let j = 0; j < n; j += 1) {
              const xv = Number(xs[j]);
              const yv = Number(ys[j]);
              if (!Number.isFinite(xv) || !Number.isFinite(yv)) {
                moveNext = true;
                continue;
              }
              const px = sx(xv);
              const py = sy(yv);
              if (!Number.isFinite(px) || !Number.isFinite(py)) {
                moveNext = true;
                continue;
              }
              points.push({ x: xv, y: yv, px, py, sourceLabel, color });
              d += (moveNext ? " M " : " L ") + px.toFixed(2) + " " + py.toFixed(2);
              moveNext = false;
            }
            if (!d) continue;
            const path = createSvgNode("path");
            path.setAttribute("d", d);
            path.setAttribute("fill", "none");
            path.setAttribute("stroke", color);
            path.setAttribute("stroke-width", String(settings.line_width));
            const dashArray = lineStyleDashArray(lineStyle, settings.line_width);
            if (dashArray) {
              path.setAttribute("stroke-dasharray", dashArray);
            }
            path.setAttribute("stroke-linejoin", "round");
            path.setAttribute("stroke-linecap", "round");
            svg.appendChild(path);
            points.sort(function(a, b) { return a.px - b.px; });
            hoverSeries.push({ points, sourceLabel, color });
          }

          let cursor = null;
          if (settings.show_cursor) {
            cursor = createSvgNode("line");
            cursor.setAttribute("class", "catnip-plot1d-cursor-line");
            cursor.setAttribute("x1", String(pad.left));
            cursor.setAttribute("x2", String(pad.left));
            cursor.setAttribute("y1", String(pad.top));
            cursor.setAttribute("y2", String(pad.top + plotH));
            cursor.setAttribute("stroke", settings.cursor_color || "#111111");
            cursor.setAttribute("stroke-width", "2");
            cursor.setAttribute("opacity", "0.85");
            svg.appendChild(cursor);
          }

          const xLabel = String(plot.x_label || "");
          if (xLabel) {
            const label = createSvgNode("text");
            label.setAttribute("x", String(pad.left + plotW / 2));
            label.setAttribute("y", String(height - 10));
            label.setAttribute("text-anchor", "middle");
            label.setAttribute("font-size", "13");
            label.setAttribute("fill", "#333333");
            label.textContent = xLabel;
            svg.appendChild(label);
          }

          const hoverGroup = createSvgNode("g");
          hoverGroup.setAttribute("display", "none");
          hoverGroup.setAttribute("pointer-events", "none");

          const hoverLine = createSvgNode("line");
          hoverLine.setAttribute("y1", String(pad.top));
          hoverLine.setAttribute("y2", String(pad.top + plotH));
          hoverLine.setAttribute("stroke", "#4a4a4a");
          hoverLine.setAttribute("stroke-width", "1");
          hoverLine.setAttribute("stroke-dasharray", "3 3");
          hoverLine.setAttribute("opacity", "0.75");
          hoverGroup.appendChild(hoverLine);

          const hoverYLine = createSvgNode("line");
          hoverYLine.setAttribute("x1", String(pad.left));
          hoverYLine.setAttribute("x2", String(pad.left + plotW));
          hoverYLine.setAttribute("stroke", "#4a4a4a");
          hoverYLine.setAttribute("stroke-width", "1");
          hoverYLine.setAttribute("stroke-dasharray", "3 3");
          hoverYLine.setAttribute("opacity", "0.75");
          hoverGroup.appendChild(hoverYLine);

          const hoverPoint = createSvgNode("circle");
          hoverPoint.setAttribute("r", "4");
          hoverPoint.setAttribute("fill", "#ffffff");
          hoverPoint.setAttribute("stroke-width", "2");
          hoverGroup.appendChild(hoverPoint);
          svg.appendChild(hoverGroup);

          const hoverTip = document.createElement("div");
          hoverTip.className = "catnip-plot-hover-tip";
          hoverTip.style.display = "none";
          el.appendChild(hoverTip);

          el.__catnipPlotMeta = {
            xMin: xAxis.min,
            xMax: xAxis.max,
            yMin: yAxis.min,
            yMax: yAxis.max,
            dataXMin,
            dataXMax,
            xAxis,
            yAxis,
            defaultXAxis,
            defaultYAxis,
            sx,
            sy,
            pad,
            plotW,
            plotH,
            cursor,
            hoverSeries,
            hoverGroup,
            hoverLine,
            hoverYLine,
            hoverPoint,
            hoverTip,
          };
        }

        function renderAllPlot1d() {
          const plots = getGridPlots();
          for (const el of plots) {
            renderPlot1d(el);
          }
          return plots;
        }

        function getPlotTimelineBounds(plots) {
          let start = Infinity;
          let end = -Infinity;
          for (const el of (plots || [])) {
            const plot = parsePlotData(el);
            const xmin = finiteNumber(plot.data_x_min, finiteNumber(plot.x_min, NaN));
            const xmax = finiteNumber(plot.data_x_max, finiteNumber(plot.x_max, NaN));
            if (Number.isFinite(xmin)) start = Math.min(start, xmin);
            if (Number.isFinite(xmax)) end = Math.max(end, xmax);
          }
          if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
          if (Math.abs(end - start) <= 1e-12) end = start + 1;
          return { start, end };
        }

        function getMediaTimelineBounds(videos, plots) {
          const sequences = getGridImageSequences();
          const timeline = getPhysicalTimeline(sequences, plots || getGridPlots());
          if (timeline.length) {
            return {
              start: timeline[0],
              end: timeline[timeline.length - 1],
              usesVideos: false,
              usesImageSequence: !!sequences.length,
              usesPhysicalTimeline: true,
            };
          }

          const sequenceCount = getCommonImageSequenceFrameCount(sequences);
          if (sequenceCount !== null) {
            return { start: 0, end: Math.max(0, sequenceCount - 1), usesVideos: false, usesImageSequence: true, usesPhysicalTimeline: false };
          }
          const videoEnd = getCommonEndTime(videos || []);
          if (videoEnd !== null) {
            return { start: 0, end: videoEnd, usesVideos: true, usesImageSequence: false, usesPhysicalTimeline: false };
          }
          const plotBounds = getPlotTimelineBounds(plots || getGridPlots());
          if (plotBounds) {
            return { start: plotBounds.start, end: plotBounds.end, usesVideos: false, usesImageSequence: false, usesPhysicalTimeline: false };
          }
          return { start: 0, end: 0, usesVideos: false, usesImageSequence: false, usesPhysicalTimeline: false };
        }

        function clampTimeForMedia(rawTime, videos, plots) {
          const bounds = getMediaTimelineBounds(videos || [], plots || getGridPlots());
          let t = Number(rawTime);
          if (!Number.isFinite(t)) t = bounds.start;
          t = Math.max(bounds.start, t);
          t = Math.min(t, bounds.end);
          return t;
        }

        function updatePlotCursors(rawTime, videos) {
          const plots = renderAllPlot1d();
          if (!plots.length) return;
          const bounds = getMediaTimelineBounds(videos || [], plots);
          const t = clampTimeForMedia(rawTime, videos || [], plots);
          const denom = Math.max(1e-12, bounds.end - bounds.start);
          const progress = (bounds.usesVideos || (bounds.usesImageSequence && !bounds.usesPhysicalTimeline))
            ? ((t - bounds.start) / denom)
            : null;
          for (const el of plots) {
            const meta = el.__catnipPlotMeta;
            if (!meta || !meta.cursor) continue;
            const cursorValue = progress === null
              ? t
              : meta.dataXMin + Math.max(0, Math.min(1, progress)) * (meta.dataXMax - meta.dataXMin);
            const clampedValue = Math.max(meta.xMin, Math.min(meta.xMax, cursorValue));
            const px = meta.sx(clampedValue);
            if (!Number.isFinite(px)) {
              meta.cursor.setAttribute("display", "none");
              continue;
            }
            meta.cursor.removeAttribute("display");
            meta.cursor.setAttribute("x1", String(px));
            meta.cursor.setAttribute("x2", String(px));
          }
        }

        function hidePlotHover(el) {
          const meta = el && el.__catnipPlotMeta;
          if (!meta) return;
          if (meta.hoverGroup) meta.hoverGroup.setAttribute("display", "none");
          if (meta.hoverTip) meta.hoverTip.style.display = "none";
        }

        function hideAllPlotHovers() {
          for (const el of getGridPlots()) {
            hidePlotHover(el);
          }
        }

        function nearestPointInSeries(points, x, y) {
          if (!points || !points.length) return null;
          let lo = 0;
          let hi = points.length;
          while (lo < hi) {
            const mid = Math.floor((lo + hi) / 2);
            if (points[mid].px < x) lo = mid + 1;
            else hi = mid;
          }

          let best = null;
          const start = Math.max(0, lo - 4);
          const end = Math.min(points.length - 1, lo + 4);
          for (let i = start; i <= end; i += 1) {
            const p = points[i];
            const dx = p.px - x;
            const dy = p.py - y;
            const score = (dx * dx) + (dy * dy);
            if (!best || score < best.score) {
              best = { point: p, score };
            }
          }
          return best;
        }

        function nearestPlotHoverPoint(meta, x, y) {
          let best = null;
          for (const item of (meta.hoverSeries || [])) {
            const candidate = nearestPointInSeries(item.points || [], x, y);
            if (candidate && (!best || candidate.score < best.score)) {
              best = candidate;
            }
          }
          return best ? best.point : null;
        }

        function updatePlotHover(el, event) {
          if (!el || !event) return;
          renderPlot1d(el);
          const meta = el.__catnipPlotMeta;
          const ctrlActive = !!(event.ctrlKey || window.__catnipPlotCtrlDown) && !event.shiftKey;
          if (!meta || !meta.hoverGroup || !meta.hoverTip || !ctrlActive) {
            hidePlotHover(el);
            return;
          }

          const rect = el.getBoundingClientRect();
          const x = Number(event.clientX) - rect.left;
          const y = Number(event.clientY) - rect.top;
          const left = meta.pad.left;
          const right = meta.pad.left + meta.plotW;
          const top = meta.pad.top;
          const bottom = meta.pad.top + meta.plotH;
          if (!Number.isFinite(x) || !Number.isFinite(y) || x < left || x > right || y < top || y > bottom) {
            hidePlotHover(el);
            return;
          }

          const point = nearestPlotHoverPoint(meta, x, y);
          if (!point) {
            hidePlotHover(el);
            return;
          }

          meta.hoverLine.setAttribute("x1", String(point.px));
          meta.hoverLine.setAttribute("x2", String(point.px));
          if (meta.hoverYLine) {
            meta.hoverYLine.setAttribute("y1", String(point.py));
            meta.hoverYLine.setAttribute("y2", String(point.py));
          }
          meta.hoverPoint.setAttribute("cx", String(point.px));
          meta.hoverPoint.setAttribute("cy", String(point.py));
          meta.hoverPoint.setAttribute("stroke", point.color || "#1565c0");
          meta.hoverGroup.removeAttribute("display");

          const lines = [];
          if ((meta.hoverSeries || []).length > 1 && point.sourceLabel) {
            lines.push(point.sourceLabel);
          }
          lines.push("x: " + formatPlotHoverValue(point.x));
          lines.push("y: " + formatPlotHoverValue(point.y));
          meta.hoverTip.textContent = lines.join("\\n");
          meta.hoverTip.style.display = "block";
          meta.hoverTip.style.left = "0px";
          meta.hoverTip.style.top = "0px";
          meta.hoverTip.style.borderColor = point.color || "#1565c0";

          const tipW = meta.hoverTip.offsetWidth || 90;
          const tipH = meta.hoverTip.offsetHeight || 42;
          let tipX = point.px + 8;
          let tipY = point.py - tipH - 8;
          if (tipX + tipW > rect.width - 4) tipX = point.px - tipW - 8;
          if (tipY < 4) tipY = point.py + 8;
          if (tipY + tipH > rect.height - 4) tipY = rect.height - tipH - 4;
          if (tipX < 4) tipX = 4;
          meta.hoverTip.style.left = String(Math.round(tipX)) + "px";
          meta.hoverTip.style.top = String(Math.round(tipY)) + "px";
        }

        function setupPlotHoverHandlers() {
          if (window.__catnipPlotHoverHandlersInit) return;
          window.__catnipPlotHoverHandlersInit = true;
          window.__catnipPlotCtrlDown = false;
          let plotViewDrag = null;
          let suppressPlotViewClick = false;

          function plotElementFromEvent(e) {
            const target = e && e.target;
            return target && target.closest ? target.closest(".catnip-plot1d") : null;
          }

          function beginPlotViewDrag(e, el, mode) {
            renderPlot1d(el);
            const meta = el.__catnipPlotMeta;
            if (!meta || !meta.xAxis || !meta.yAxis) return;
            const point = plotLocalPoint(el, e);
            plotViewDrag = {
              el,
              mode,
              startX: Number(e.clientX) || 0,
              startY: Number(e.clientY) || 0,
              pointerId: e.pointerId,
              moved: false,
              xAxis: meta.xAxis,
              yAxis: meta.yAxis,
              plotW: Math.max(1, meta.plotW),
              plotH: Math.max(1, meta.plotH),
              centerX: plotAxisTForLocalPoint(meta.xAxis, meta, point, "x"),
              centerY: plotAxisTForLocalPoint(meta.yAxis, meta, point, "y"),
            };
            el.classList.add(mode === "zoom" ? "is-zooming" : "is-panning");
            document.body.classList.add(mode === "zoom" ? "catnip-plot-zooming" : "catnip-plot-panning");
            hidePlotHover(el);
            try {
              el.setPointerCapture(e.pointerId);
            } catch (_) {
              // Pointer capture is best-effort; document listeners keep the drag alive.
            }
            e.preventDefault();
            e.stopPropagation();
          }

          function updatePlotViewDrag(e) {
            if (!plotViewDrag) return;
            const drag = plotViewDrag;
            const dx = (Number(e.clientX) || 0) - drag.startX;
            const dy = (Number(e.clientY) || 0) - drag.startY;
            if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
              drag.moved = true;
            }

            let nextXAxis = null;
            let nextYAxis = null;
            if (drag.mode === "pan") {
              const xSpan = drag.xAxis.tMax - drag.xAxis.tMin;
              const ySpan = drag.yAxis.tMax - drag.yAxis.tMin;
              const nextXMin = drag.xAxis.tMin - (dx / drag.plotW) * xSpan;
              const nextXMax = drag.xAxis.tMax - (dx / drag.plotW) * xSpan;
              const nextYMin = drag.yAxis.tMin + (dy / drag.plotH) * ySpan;
              const nextYMax = drag.yAxis.tMax + (dy / drag.plotH) * ySpan;
              nextXAxis = plotAxisFromTransformRange(drag.xAxis, nextXMin, nextXMax);
              nextYAxis = plotAxisFromTransformRange(drag.yAxis, nextYMin, nextYMax);
            } else {
              const rangeFactor = Math.exp(dy * 0.01);
              nextXAxis = zoomPlotAxisAround(drag.xAxis, drag.centerX, rangeFactor);
              nextYAxis = zoomPlotAxisAround(drag.yAxis, drag.centerY, rangeFactor);
            }

            if (nextXAxis && nextYAxis) {
              setPlotViewStateFromAxes(drag.el, nextXAxis, nextYAxis);
              rerenderPlotView(drag.el);
            }
            e.preventDefault();
            e.stopPropagation();
          }

          function finishPlotViewDrag(e) {
            if (!plotViewDrag) return;
            const drag = plotViewDrag;
            drag.el.classList.remove("is-panning");
            drag.el.classList.remove("is-zooming");
            document.body.classList.remove("catnip-plot-panning");
            document.body.classList.remove("catnip-plot-zooming");
            try {
              if (drag.pointerId !== undefined) {
                drag.el.releasePointerCapture(drag.pointerId);
              }
            } catch (_) {
              // Ignore release failures for pointers that were not captured.
            }
            suppressPlotViewClick = !!drag.moved;
            plotViewDrag = null;
            if (e) {
              e.preventDefault();
              e.stopPropagation();
            }
          }

          document.addEventListener("keydown", function(e) {
            if (e && e.key === "Control") {
              window.__catnipPlotCtrlDown = true;
            }
          });
          document.addEventListener("keyup", function(e) {
            if (e && e.key === "Control") {
              window.__catnipPlotCtrlDown = false;
              hideAllPlotHovers();
            }
          });
          window.addEventListener("blur", function() {
            window.__catnipPlotCtrlDown = false;
            hideAllPlotHovers();
          });
          document.addEventListener("pointermove", function(e) {
            if (plotViewDrag) {
              updatePlotViewDrag(e);
              return;
            }
            const el = plotElementFromEvent(e);
            if (!el) return;
            const ctrlActive = !!(e.ctrlKey || window.__catnipPlotCtrlDown) && !e.shiftKey;
            if (!ctrlActive) {
              hidePlotHover(el);
              return;
            }
            updatePlotHover(el, e);
          });
          document.addEventListener("pointerdown", function(e) {
            const el = plotElementFromEvent(e);
            if (!el) return;
            const ctrlActive = !!(e.ctrlKey || window.__catnipPlotCtrlDown);
            const isShiftPan = e.button === 0 && e.shiftKey && !ctrlActive;
            const isMiddleZoom = e.button === 1;
            if (isShiftPan || isMiddleZoom) {
              beginPlotViewDrag(e, el, isMiddleZoom ? "zoom" : "pan");
              return;
            }
            if (el && e.ctrlKey && e.button === 0) {
              e.preventDefault();
              e.stopPropagation();
            }
          }, true);
          document.addEventListener("pointerup", finishPlotViewDrag, true);
          document.addEventListener("pointercancel", finishPlotViewDrag, true);
          document.addEventListener("wheel", function(e) {
            const el = plotElementFromEvent(e);
            if (!el) return;
            const rangeFactor = Math.exp((Number(e.deltaY) || 0) * 0.0015);
            zoomPlotViewAt(el, e, rangeFactor);
            hidePlotHover(el);
            e.preventDefault();
            e.stopPropagation();
          }, { capture: true, passive: false });
          document.addEventListener("dblclick", function(e) {
            const el = plotElementFromEvent(e);
            if (!el) return;
            resetPlotView(el);
            e.preventDefault();
            e.stopPropagation();
          }, true);
          document.addEventListener("auxclick", function(e) {
            const el = plotElementFromEvent(e);
            if (el && e.button === 1) {
              e.preventDefault();
              e.stopPropagation();
            }
          }, true);
          document.addEventListener("click", function(e) {
            if (!suppressPlotViewClick) return;
            suppressPlotViewClick = false;
            const el = plotElementFromEvent(e);
            if (!el) return;
            e.preventDefault();
            e.stopPropagation();
          }, true);
          document.addEventListener("contextmenu", function(e) {
            const el = plotElementFromEvent(e);
            if (el && e.ctrlKey) {
              e.preventDefault();
              e.stopPropagation();
            }
          }, true);
          document.addEventListener("pointerout", function(e) {
            const el = plotElementFromEvent(e);
            if (!el) return;
            if (!e.relatedTarget || !el.contains(e.relatedTarget)) {
              hidePlotHover(el);
            }
          });
        }

        function scheduleRenderAllPlot1d() {
          if (window.__catnipPlotRenderTimer) {
            clearTimeout(window.__catnipPlotRenderTimer);
          }
          window.__catnipPlotRenderTimer = setTimeout(function() {
            renderAllPlot1d();
            updatePlotCursors(window.__catnipGridSyncTime || 0, getGridVideos());
          }, 30);
        }
        window.catnipScheduleRenderAllPlot1d = scheduleRenderAllPlot1d;

        function observePlot1dSizes() {
          if (!window.ResizeObserver) return;
          if (!window.__catnipPlotResizeObserver) {
            window.__catnipPlotResizeObserver = new ResizeObserver(function() {
              scheduleRenderAllPlot1d();
            });
          }
          const resizeObserver = window.__catnipPlotResizeObserver;
          for (const el of getGridPlots()) {
            if (!el.__catnipPlotResizeObserved) {
              resizeObserver.observe(el);
              el.__catnipPlotResizeObserved = true;
            }
          }
        }

        function setupPlot1dObserver() {
          setupPlotHoverHandlers();
          if (window.__catnipPlotObserverInit) return;
          window.__catnipPlotObserverInit = true;
          const observer = new MutationObserver(function() {
            observePlot1dSizes();
            scheduleRenderAllPlot1d();
          });
          observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-plot", "data-plot-settings"] });
          window.addEventListener("resize", scheduleRenderAllPlot1d);
          observePlot1dSizes();
          scheduleRenderAllPlot1d();
        }

        function getCommonEndTime(videos) {
          const count = getCommonVideoFrameCount(videos);
          if (count !== null) {
            return timeForFrameOrdinal(Math.max(0, count - 1), videos);
          }
          let minDuration = Infinity;
          for (const v of videos) {
            const d = Number(v && v.duration);
            if (Number.isFinite(d) && d > 0) {
              minDuration = Math.min(minDuration, d);
            }
          }
          if (!Number.isFinite(minDuration)) {
            return null;
          }
          return Math.max(0, minDuration - 0.04);
        }

        function clampTimeForVideos(rawTime, videos) {
          return clampTimeForMedia(rawTime, videos || [], getGridPlots());
        }

        function getReferenceTime(videos) {
          for (const v of videos) {
            const t = Number(v && v.currentTime);
            if (Number.isFinite(t) && t >= 0) {
              return t;
            }
          }
          return 0;
        }

        function inferFrameStepSeconds(videos, plots) {
          if (videos && videos.length) {
            const fps = inferFpsForVideos(videos);
            return 1.0 / fps;
          }
          const bounds = getMediaTimelineBounds(videos || [], plots || getGridPlots());
          const range = Math.max(1e-12, bounds.end - bounds.start);
          return range / 200.0;
        }

        function setAllVideoTimes(videos, rawTime) {
          const t = clampTimeForVideos(rawTime, videos);
          for (const v of videos) {
            try {
              v.currentTime = t;
            } catch (_err) {
              // Ignore seek errors for unloaded videos.
            }
          }
          window.__catnipGridSyncTime = t;
          updatePlotCursors(t, videos);
          return t;
        }

        function pauseAllVideos(videos) {
          for (const v of videos) {
            try {
              v.pause();
            } catch (_err) {
              // Ignore pause errors.
            }
          }
        }

        function playAllVideos(videos) {
          for (const v of videos) {
            try {
              const p = v.play();
              if (p && typeof p.catch === "function") {
                p.catch(function() {});
              }
            } catch (_err) {
              // Ignore autoplay failures per stream.
            }
          }
        }

        function applyPhysicalTimelineTime(rawTime, sequences, videos, plots) {
          sequences = sequences || getGridImageSequences();
          videos = videos || getGridVideos();
          plots = plots || getGridPlots();
          const t = clampTimeForMedia(rawTime, videos, plots);
          if (sequences.length) {
            setImageSequencesForTime(t, sequences);
          }
          if (videos.length) {
            setAllVideoTimes(videos, t);
          } else {
            window.__catnipGridSyncTime = t;
            updatePlotCursors(t, videos);
          }
          gridVcrState.syncTime = t;

          const timeline = getPhysicalTimeline(sequences, plots);
          if (timeline.length) {
            gridVcrState.timelinePosition = timelineIndexNearest(t, timeline);
          }
          updateVcrTimeLabelFromSeconds(t, videos, plots);
          return t;
        }

        function stepPhysicalTimelineBy(frameCount, sequences, videos, plots) {
          sequences = sequences || getGridImageSequences();
          videos = videos || getGridVideos();
          plots = plots || getGridPlots();
          const timeline = getPhysicalTimeline(sequences, plots);
          if (!timeline.length) return null;
          const base = Number.isFinite(gridVcrState.syncTime)
            ? gridVcrState.syncTime
            : (sequences.length ? getReferenceImageSequenceTime(sequences) : timeline[0]);
          const nextIndex = Math.max(
            0,
            Math.min(timelineIndexNearest(base, timeline) + Number(frameCount || 0), timeline.length - 1)
          );
          return applyPhysicalTimelineTime(timeline[nextIndex], sequences, videos, plots);
        }

        function stopSyncTimer() {
          if (gridVcrState.syncTimer) {
            clearInterval(gridVcrState.syncTimer);
            gridVcrState.syncTimer = null;
          }
        }

        function syncGridVideosNow() {
          if (!gridVcrState.playing) {
            stopSyncTimer();
            const sequencesNow = getGridImageSequences();
            const videosNow = getGridVideos();
            const plotsNow = getGridPlots();
            if (sequencesNow.length) {
              const timelineNow = getPhysicalTimeline(sequencesNow, plotsNow);
              if (timelineNow.length) {
                const target = Number.isFinite(gridVcrState.syncTime)
                  ? gridVcrState.syncTime
                  : getReferenceImageSequenceTime(sequencesNow);
                applyPhysicalTimelineTime(target, sequencesNow, videosNow, plotsNow);
              } else {
                updateVcrTimeLabelFromSeconds(getReferenceImageSequenceFrame(sequencesNow), videosNow, plotsNow);
              }
            } else if (videosNow.length) {
              updateVcrTimeLabelFromSeconds(getReferenceTime(videosNow), videosNow);
            } else if (plotsNow.length) {
              updateVcrTimeLabelFromSeconds(gridVcrState.syncTime, [], plotsNow);
            } else {
              updateVcrTimeLabelFromSeconds(0, []);
            }
            return;
          }

          const sequences = getGridImageSequences();
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (sequences.length) {
            const timeline = getPhysicalTimeline(sequences, plots);
            if (timeline.length) {
              const now = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
              const last = Number(gridVcrState.lastTickMs);
              const dt = Number.isFinite(last) && last > 0 ? Math.max(0, (now - last) / 1000.0) : 0.16;
              gridVcrState.lastTickMs = now;
              const fps = inferFpsForImageSequences(sequences);
              let position = Number(gridVcrState.timelinePosition);
              if (!Number.isFinite(position)) {
                position = timelineIndexNearest(gridVcrState.syncTime, timeline);
              }
              const nextPosition = Math.min(Math.max(0, timeline.length - 1), position + dt * fps);
              const nextIndex = Math.max(0, Math.min(Math.floor(nextPosition + 1e-9), timeline.length - 1));
              const nextTime = timeline[nextIndex];
              setImageSequencesForTime(nextTime, sequences);
              gridVcrState.timelinePosition = nextPosition;
              gridVcrState.syncTime = nextTime;
              window.__catnipGridSyncTime = nextTime;
              updateVcrTimeLabelFromSeconds(nextTime, videos, plots);
              if (nextPosition >= Math.max(0, timeline.length - 1)) {
                gridVcrState.playing = false;
                stopSyncTimer();
              }
              return;
            }

            const count = getCommonImageSequenceFrameCount(sequences);
            if (count === null || count <= 0) {
              gridVcrState.playing = false;
              stopSyncTimer();
              updateVcrTimeLabelFromSeconds(0, videos, plots);
              return;
            }

            const now = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
            const last = Number(gridVcrState.lastTickMs);
            const dt = Number.isFinite(last) && last > 0 ? Math.max(0, (now - last) / 1000.0) : 0.16;
            gridVcrState.lastTickMs = now;
            const fps = inferFpsForImageSequences(sequences);
            const nextPosition = Math.min(Math.max(0, count - 1), Number(gridVcrState.syncTime || 0) + dt * fps);
            const nextFrame = setImageSequenceFrame(Math.floor(nextPosition + 1e-9), sequences);
            gridVcrState.syncTime = nextPosition;
            updateVcrTimeLabelFromSeconds(nextFrame, videos, plots);
            if (nextPosition >= Math.max(0, count - 1)) {
              gridVcrState.playing = false;
              stopSyncTimer();
            }
            return;
          }

          if (!videos.length) {
            if (!plots.length) {
              gridVcrState.playing = false;
              stopSyncTimer();
              updateVcrTimeLabelFromSeconds(0, []);
              return;
            }

            const now = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
            const last = Number(gridVcrState.lastTickMs);
            const dt = Number.isFinite(last) && last > 0 ? Math.max(0, (now - last) / 1000.0) : 0.16;
            gridVcrState.lastTickMs = now;
            const bounds = getMediaTimelineBounds([], plots);
            const rate = Math.max(1e-12, bounds.end - bounds.start) / 8.0;
            const next = clampTimeForMedia(gridVcrState.syncTime + dt * rate, [], plots);
            gridVcrState.syncTime = next;
            updateVcrTimeLabelFromSeconds(next, [], plots);
            if (next >= (bounds.end - 1e-9)) {
              gridVcrState.playing = false;
              stopSyncTimer();
            }
            return;
          }

          const ref = videos[0];
          const refTime = clampTimeForVideos(ref && ref.currentTime, videos);
          const commonEnd = getCommonEndTime(videos);
          if (commonEnd !== null && refTime >= (commonEnd - 0.02)) {
            pauseAllVideos(videos);
            const stopAt = setAllVideoTimes(videos, commonEnd);
            gridVcrState.syncTime = stopAt;
            gridVcrState.playing = false;
            stopSyncTimer();
            updateVcrTimeLabelFromSeconds(stopAt, videos);
            return;
          }

          gridVcrState.syncTime = refTime;
          updateVcrTimeLabelFromSeconds(refTime, videos);
          for (let i = 1; i < videos.length; i += 1) {
            const v = videos[i];
            const t = Number(v && v.currentTime);
            if (!Number.isFinite(t)) {
              continue;
            }
            if (Math.abs(t - refTime) > 0.12) {
              try {
                v.currentTime = refTime;
              } catch (_err) {
                // Ignore seek errors for unloaded streams.
              }
            }
          }
        }

        function startSyncTimer() {
          stopSyncTimer();
          gridVcrState.syncTimer = setInterval(syncGridVideosNow, 160);
        }

        function currentVcrSliderTarget(videos, plots) {
          const slider = document.getElementById("catnip-vcr-step-slider");
          if (slider) {
            const target = getVcrSliderTimeValue(videos || [], plots || []);
            if (Number.isFinite(target)) return target;
          }
          const stateTime = Number(gridVcrState.syncTime);
          if (Number.isFinite(stateTime)) return stateTime;
          const windowTime = Number(window.__catnipGridSyncTime);
          return Number.isFinite(windowTime) ? windowTime : 0;
        }

        function syncGridMediaToCurrentVcrTime() {
          const sequences = getGridImageSequences();
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!sequences.length && !videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }

          const target = currentVcrSliderTarget(videos, plots);
          if (sequences.length) {
            if (getPhysicalTimeline(sequences, plots).length) {
              applyPhysicalTimelineTime(target, sequences, videos, plots);
            } else {
              const frame = setImageSequenceFrame(target, sequences);
              gridVcrState.syncTime = frame;
              gridVcrState.timelinePosition = frame;
              updateVcrTimeLabelFromSeconds(frame, videos, plots);
            }
            return;
          }
          if (videos.length) {
            const t = setAllVideoTimes(videos, target);
            gridVcrState.syncTime = t;
            updateVcrTimeLabelFromSeconds(t, videos, plots);
            if (gridVcrState.playing) {
              playAllVideos(videos);
            } else {
              pauseAllVideos(videos);
            }
            return;
          }

          const t = clampTimeForMedia(target, [], plots);
          gridVcrState.syncTime = t;
          updateVcrTimeLabelFromSeconds(t, [], plots);
        }

        function scheduleGridMediaSyncToCurrentVcrTime() {
          if (gridMediaSyncTimer) {
            clearTimeout(gridMediaSyncTimer);
          }
          gridMediaSyncTimer = setTimeout(function() {
            gridMediaSyncTimer = null;
            syncGridMediaToCurrentVcrTime();
          }, 30);
        }

        function mutationTouchesGridMedia(mutation) {
          if (!mutation) return false;
          if (mutation.type === "attributes") {
            const target = mutation.target;
            return !!(
              target
              && target.matches
              && (
                target.matches('img[data-grid-image-sequence="1"]')
                || target.matches('video[data-grid-video="1"]')
                || target.matches(".catnip-plot1d")
                || target.matches(".catnip-dropcell")
              )
            );
          }
          for (const node of Array.from(mutation.addedNodes || [])) {
            if (!node || node.nodeType !== 1) continue;
            if (
              (node.matches && (
                node.matches('img[data-grid-image-sequence="1"]')
                || node.matches('video[data-grid-video="1"]')
                || node.matches(".catnip-plot1d")
                || node.matches(".catnip-dropcell")
              ))
              || (node.querySelector && node.querySelector(
                'img[data-grid-image-sequence="1"], video[data-grid-video="1"], .catnip-plot1d, .catnip-dropcell'
              ))
            ) {
              return true;
            }
          }
          return false;
        }

        function seekAllVideosBy(deltaSeconds) {
          const sequences = getGridImageSequences();
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!sequences.length && !videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          if (sequences.length) {
            const timeline = getPhysicalTimeline(sequences, plots);
            if (timeline.length) {
              const step = Number(deltaSeconds || 0) >= 0 ? 1 : -1;
              stepPhysicalTimelineBy(step, sequences, videos, plots);
              return;
            }
            const next = setImageSequenceFrame(
              getReferenceImageSequenceFrame(sequences) + Number(deltaSeconds || 0),
              sequences
            );
            gridVcrState.syncTime = next;
            gridVcrState.timelinePosition = next;
            updateVcrTimeLabelFromSeconds(next, videos, plots);
            return;
          }
          const base = clampTimeForMedia(
            Number.isFinite(gridVcrState.syncTime) ? gridVcrState.syncTime : getReferenceTime(videos),
            videos,
            plots
          );
          const next = setAllVideoTimes(videos, base + deltaSeconds);
          gridVcrState.syncTime = next;
          updateVcrTimeLabelFromSeconds(next, videos, plots);
          if (gridVcrState.playing) {
            if (videos.length) playAllVideos(videos);
            gridVcrState.lastTickMs = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
            startSyncTimer();
          } else {
            pauseAllVideos(videos);
          }
        }

        function stepAllVideosByFrames(frameCount) {
          const sequences = getGridImageSequences();
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!sequences.length && !videos.length && !plots.length) return;
          const timeline = getPhysicalTimeline(sequences, plots);
          if (timeline.length && !videos.length) {
            stepPhysicalTimelineBy(frameCount, sequences, videos, plots);
            if (!gridVcrState.playing) pauseAllVideos(videos);
            return;
          }
          if (sequences.length) {
            const next = setImageSequenceFrame(
              getReferenceImageSequenceFrame(sequences) + Number(frameCount || 0),
              sequences
            );
            gridVcrState.syncTime = next;
            gridVcrState.timelinePosition = next;
            updateVcrTimeLabelFromSeconds(next, videos, plots);
            if (!gridVcrState.playing) pauseAllVideos(videos);
            return;
          }
          if (videos.length) {
            const count = getCommonVideoFrameCount(videos);
            if (count !== null) {
              const baseTime = clampTimeForMedia(
                Number.isFinite(gridVcrState.syncTime) ? gridVcrState.syncTime : getReferenceTime(videos),
                videos,
                plots
              );
              const baseOrdinal = frameOrdinalFromTime(baseTime, videos);
              const nextOrdinal = Math.max(
                0,
                Math.min(baseOrdinal + Number(frameCount || 0), Math.max(0, count - 1))
              );
              const next = setAllVideoTimes(videos, timeForFrameOrdinal(nextOrdinal, videos));
              gridVcrState.syncTime = next;
              updateVcrTimeLabelFromSeconds(next, videos, plots);
              if (gridVcrState.playing) {
                playAllVideos(videos);
                gridVcrState.lastTickMs = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
                startSyncTimer();
              } else {
                pauseAllVideos(videos);
              }
              return;
            }
          }
          const frameStep = inferFrameStepSeconds(videos, plots);
          seekAllVideosBy(frameStep * Number(frameCount || 0));
        }

        function seekAllVideosToSlider() {
          const sequences = getGridImageSequences();
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!sequences.length && !videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const targetSeconds = getVcrSliderTimeValue(videos, plots);
          if (sequences.length) {
            if (getPhysicalTimeline(sequences, plots).length) {
              applyPhysicalTimelineTime(targetSeconds, sequences, videos, plots);
            } else {
              const frame = setImageSequenceFrame(targetSeconds, sequences);
              gridVcrState.syncTime = frame;
              gridVcrState.timelinePosition = frame;
              updateVcrTimeLabelFromSeconds(frame, videos, plots);
            }
            return;
          }
          const t = setAllVideoTimes(videos, targetSeconds);
          gridVcrState.syncTime = t;
          updateVcrTimeLabelFromSeconds(t, videos, plots);
          if (gridVcrState.playing) {
            if (videos.length) playAllVideos(videos);
            gridVcrState.lastTickMs = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
            startSyncTimer();
          } else {
            pauseAllVideos(videos);
          }
        }

        function setAllToStart() {
          const sequences = getGridImageSequences();
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!sequences.length && !videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const timeline = getPhysicalTimeline(sequences, plots);
          if (timeline.length && !videos.length) {
            applyPhysicalTimelineTime(timeline[0], sequences, videos, plots);
            return;
          }
          if (sequences.length) {
            const frame = setImageSequenceFrame(0, sequences);
            gridVcrState.syncTime = frame;
            gridVcrState.timelinePosition = frame;
            updateVcrTimeLabelFromSeconds(frame, videos, plots);
            return;
          }
          const bounds = getMediaTimelineBounds(videos, plots);
          const t = setAllVideoTimes(videos, bounds.start);
          gridVcrState.syncTime = t;
          updateVcrTimeLabelFromSeconds(t, videos, plots);
          if (gridVcrState.playing) {
            if (videos.length) playAllVideos(videos);
            gridVcrState.lastTickMs = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
            startSyncTimer();
          } else {
            pauseAllVideos(videos);
          }
        }

        function setAllToEnd() {
          const sequences = getGridImageSequences();
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!sequences.length && !videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const timeline = getPhysicalTimeline(sequences, plots);
          if (timeline.length && !videos.length) {
            applyPhysicalTimelineTime(timeline[timeline.length - 1], sequences, videos, plots);
            return;
          }
          if (sequences.length) {
            const count = getCommonImageSequenceFrameCount(sequences);
            const frame = setImageSequenceFrame(count !== null ? Math.max(0, count - 1) : 0, sequences);
            gridVcrState.syncTime = frame;
            gridVcrState.timelinePosition = frame;
            updateVcrTimeLabelFromSeconds(frame, videos, plots);
            return;
          }
          const bounds = getMediaTimelineBounds(videos, plots);
          const target = bounds.end;
          const t = setAllVideoTimes(videos, target);
          gridVcrState.syncTime = t;
          updateVcrTimeLabelFromSeconds(t, videos, plots);
          if (gridVcrState.playing) {
            if (videos.length) playAllVideos(videos);
            gridVcrState.lastTickMs = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
            startSyncTimer();
          } else {
            pauseAllVideos(videos);
          }
        }

        function playAllFromSyncTime() {
          const sequences = getGridImageSequences();
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!sequences.length && !videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const timeline = getPhysicalTimeline(sequences, plots);
          if (timeline.length && !videos.length) {
            const base = Number.isFinite(gridVcrState.syncTime)
              ? clampTimeForMedia(gridVcrState.syncTime, videos, plots)
              : timeline[0];
            applyPhysicalTimelineTime(base, sequences, videos, plots);
            gridVcrState.timelinePosition = timelineIndexNearest(base, timeline);
            gridVcrState.playing = true;
            gridVcrState.lastTickMs = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
            startSyncTimer();
            return;
          }
          if (sequences.length) {
            const frame = setImageSequenceFrame(
              Number.isFinite(gridVcrState.syncTime) ? gridVcrState.syncTime : getReferenceImageSequenceFrame(sequences),
              sequences
            );
            gridVcrState.syncTime = frame;
            gridVcrState.timelinePosition = frame;
            updateVcrTimeLabelFromSeconds(frame, videos, plots);
            gridVcrState.playing = true;
            gridVcrState.lastTickMs = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
            startSyncTimer();
            return;
          }
          const base = setAllVideoTimes(
            videos,
            Number.isFinite(gridVcrState.syncTime) ? gridVcrState.syncTime : getReferenceTime(videos)
          );
          gridVcrState.syncTime = base;
          updateVcrTimeLabelFromSeconds(base, videos, plots);
          gridVcrState.playing = true;
          gridVcrState.lastTickMs = (window.performance && window.performance.now) ? window.performance.now() : Date.now();
          if (videos.length) playAllVideos(videos);
          startSyncTimer();
        }

        function pauseAllAtCurrentTime() {
          const sequences = getGridImageSequences();
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!sequences.length && !videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const timeline = getPhysicalTimeline(sequences, plots);
          if (timeline.length && !videos.length) {
            gridVcrState.syncTime = clampTimeForMedia(gridVcrState.syncTime, videos, plots);
            gridVcrState.timelinePosition = timelineIndexNearest(gridVcrState.syncTime, timeline);
            setImageSequencesForTime(gridVcrState.syncTime, sequences);
          } else {
            gridVcrState.syncTime = sequences.length
              ? getReferenceImageSequenceFrame(sequences)
              : clampTimeForMedia(videos.length ? getReferenceTime(videos) : gridVcrState.syncTime, videos, plots);
            gridVcrState.timelinePosition = gridVcrState.syncTime;
          }
          gridVcrState.playing = false;
          stopSyncTimer();
          pauseAllVideos(videos);
          updateVcrTimeLabelFromSeconds(gridVcrState.syncTime, videos, plots);
        }

        function stopAllVideos() {
          const sequences = getGridImageSequences();
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!sequences.length && !videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          gridVcrState.playing = false;
          stopSyncTimer();
          pauseAllVideos(videos);
          const timeline = getPhysicalTimeline(sequences, plots);
          if (timeline.length && !videos.length) {
            applyPhysicalTimelineTime(timeline[0], sequences, videos, plots);
            return;
          }
          if (sequences.length) {
            gridVcrState.syncTime = setImageSequenceFrame(0, sequences);
            gridVcrState.timelinePosition = gridVcrState.syncTime;
            updateVcrTimeLabelFromSeconds(gridVcrState.syncTime, videos, plots);
            return;
          }
          const bounds = getMediaTimelineBounds(videos, plots);
          gridVcrState.syncTime = setAllVideoTimes(videos, bounds.start);
          updateVcrTimeLabelFromSeconds(gridVcrState.syncTime, videos, plots);
        }

        function runGridVcrAction(action) {
          const a = String(action || "").trim().toLowerCase();
          if (!a) return;
          if (a === "start") {
            setAllToStart();
            return;
          }
          if (a === "frameback") {
            stepAllVideosByFrames(-1);
            return;
          }
          if (a === "frame") {
            stepAllVideosByFrames(1);
            return;
          }
          if (a === "slider") {
            seekAllVideosToSlider();
            return;
          }
          if (a === "back") {
            stepAllVideosByFrames(-1);
            return;
          }
          if (a === "play") {
            playAllFromSyncTime();
            return;
          }
          if (a === "pause") {
            pauseAllAtCurrentTime();
            return;
          }
          if (a === "stop") {
            stopAllVideos();
            return;
          }
          if (a === "forward") {
            stepAllVideosByFrames(1);
            return;
          }
          if (a === "end") {
            setAllToEnd();
          }
        }

        window.__catnipMainGridVcr = runGridVcrAction;
        window.catnipGridVcr = runGridVcrAction;

        const gridMediaObserver = new MutationObserver(function(mutations) {
          if ((mutations || []).some(mutationTouchesGridMedia)) {
            scheduleGridMediaSyncToCurrentVcrTime();
          }
        });
        gridMediaObserver.observe(document.body, {
          childList: true,
          subtree: true,
          attributes: true,
          attributeFilter: ["data-frame-count", "data-frame-indices", "data-frame-sources", "data-time-values", "data-time-mode", "data-plot", "data-plot-settings", "data-timeline-driver"],
        });
        scheduleGridMediaSyncToCurrentVcrTime();

        document.addEventListener("dragstart", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;
          if (!e.dataTransfer) return;

          const varEl = target.closest(".catnip-draggable-var");
          if (varEl) {
            const item = varEl.getAttribute("data-item") || "";
            if (!item) return;
            e.dataTransfer.setData("text/plain", item);
            e.dataTransfer.setData("application/x-catnip-var", item);
            e.dataTransfer.effectAllowed = "copy";
            varEl.style.opacity = "0.45";
            return;
          }

          const cellEl = target.closest(".catnip-dropcell");
          if (!cellEl) return;
          const filled = cellEl.getAttribute("data-cell-filled");
          const fromIdx = cellEl.getAttribute("data-cell-index");
          if (filled !== "1" || fromIdx === null) return;
          e.dataTransfer.setData("application/x-catnip-grid-cell", fromIdx);
          e.dataTransfer.effectAllowed = "move";
          cellEl.style.opacity = "0.55";
        });

        document.addEventListener("dragend", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;
          const varEl = target.closest(".catnip-draggable-var");
          if (varEl) varEl.style.opacity = "1";
          const cellEl = target.closest(".catnip-dropcell");
          if (cellEl) cellEl.style.opacity = "1";
        });

        document.addEventListener("dragover", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;
          const el = target.closest(".catnip-dropcell");
          if (!el) return;
          e.preventDefault();
          if (e.dataTransfer) {
            const types = Array.from(e.dataTransfer.types || []);
            e.dataTransfer.dropEffect = types.includes("application/x-catnip-grid-cell") ? "move" : "copy";
          }
          el.classList.add("catnip-drop-hover");
        });

        document.addEventListener("dragleave", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;
          const el = target.closest(".catnip-dropcell");
          if (!el) return;
          if (!el.contains(e.relatedTarget)) {
            el.classList.remove("catnip-drop-hover");
          }
        });

        document.addEventListener("drop", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;
          const el = target.closest(".catnip-dropcell");
          if (!el) return;
          e.preventDefault();
          el.classList.remove("catnip-drop-hover");
          const fromCell = e.dataTransfer ? (e.dataTransfer.getData("application/x-catnip-grid-cell") || "") : "";
          const idx = el.getAttribute("data-cell-index");
          if (fromCell !== "" && idx !== null) {
            if (window.trame && window.trame.trigger) {
              window.trame.trigger("move_grid_cell_trigger", [fromCell, idx]);
            }
            return;
          }
          const item = e.dataTransfer
            ? (e.dataTransfer.getData("text/plain") || e.dataTransfer.getData("application/x-catnip-var") || "")
            : "";
          if (!item || idx === null) return;
          if (window.trame && window.trame.trigger) {
            window.trame.trigger("assign_var_to_grid_cell_trigger", [item, idx]);
          }
        });

        document.addEventListener("contextmenu", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;

          if (target.closest("#catnip-context-menu")) return;

          const itemEl = target.closest(".catnip-draggable-var");
          if (itemEl) {
            e.preventDefault();
            const item = itemEl.getAttribute("data-item") || "";
            if (item && window.trame && window.trame.trigger) {
              window.trame.trigger("show_item_context_menu", [item, (e.clientX || 0), (e.clientY || 0)]);
            }
            return;
          }

          const cellEl = target.closest(".catnip-dropcell");
          if (cellEl) {
            e.preventDefault();
            const idx = cellEl.getAttribute("data-cell-index");
            if (idx !== null && window.trame && window.trame.trigger) {
              window.trame.trigger("show_cell_context_menu", [idx, (e.clientX || 0), (e.clientY || 0)]);
            }
            return;
          }

          if (window.trame && window.trame.trigger) {
            window.trame.trigger("hide_context_menu_trigger", []);
          }
        });

        document.addEventListener("click", function(e) {
          const target = e && e.target;
          const vcrBtn = target && target.closest ? target.closest("[data-vcr-action]") : null;
          if (vcrBtn) {
            e.preventDefault();
            runGridVcrAction(vcrBtn.getAttribute("data-vcr-action") || "");
          }
          if (!target || !target.closest || !target.closest("#catnip-context-menu")) {
            if (window.trame && window.trame.trigger) {
              window.trame.trigger("hide_context_menu_trigger", []);
            }
          }
        });

        document.addEventListener("loadedmetadata", function(e) {
          const target = e && e.target;
          if (!isGridVideo(target)) return;
          const videos = getGridVideos();
          if (!videos.length) return;
          const t = setAllVideoTimes(videos, gridVcrState.syncTime);
          gridVcrState.syncTime = t;
          updateVcrTimeLabelFromSeconds(t, videos);
          if (gridVcrState.playing) {
            playAllVideos(videos);
            startSyncTimer();
          }
        }, true);

        document.addEventListener("ended", function(e) {
          const target = e && e.target;
          if (!isGridVideo(target)) return;
          if (!gridVcrState.playing) return;
          const videos = getGridVideos();
          if (!videos.length) return;
          gridVcrState.playing = false;
          stopSyncTimer();
          pauseAllVideos(videos);
          const endTime = getCommonEndTime(videos);
          const t = setAllVideoTimes(videos, endTime !== null ? endTime : getReferenceTime(videos));
          gridVcrState.syncTime = t;
          updateVcrTimeLabelFromSeconds(t, videos);
        }, true);
      } catch (err) {
        console.error("catnip drag/drop init failed", err);
      }
    })();
    """

    with SinglePageLayout(server) as layout:
        layout.title.set_text(
            f"Campaign loaded: {campaign_name}" if campaign_name else "Campaign loaded"
        )

        with layout.toolbar:
            html.Span("Query:", class_="text-caption ml-4")
            vuetify.VBtn(
                "?",
                click=ctrl.show_query_help,
                variant="tonal",
                size="small",
                min_width=32,
                title="Query help",
            )
            vuetify.VTextField(
                v_model=("queryText",),
                placeholder="e.g. var == 'rho' and source_dataset == 'hll_128/output.bp'",
                density="compact",
                hide_details=True,
                variant="outlined",
                style="max-width: 420px;",
                class_="mx-2",
            )
            vuetify.VBtn("Query", click=ctrl.run_query, variant="outlined", size="small")
            vuetify.VBtn("Clear", click=ctrl.clear_query, variant="text", size="small", class_="ml-1")
            with vuetify.Template(v_if="queryError"):
                html.Span("{{ queryError }}", class_="text-caption ml-2", style="color:#b00020;")

        with layout.content:
            client.Script(drag_drop_js)
            client.Style(
                """
                .catnip-draggable-var { cursor: grab; user-select: none; }
                .catnip-draggable-var:active { cursor: grabbing; }
                .catnip-var-list { padding: 4px 2px; }
                .catnip-var-group {
                  margin: 6px 6px 10px;
                  padding: 6px 6px 8px;
                  border: 1px solid #b8c4d1;
                  border-radius: 6px;
                  background: #f4f7fa;
                  box-shadow: inset 0 0 0 1px #e2e8ef;
                }
                .catnip-var-group-title {
                  padding: 4px 8px;
                  width: 100%;
                  border: 0;
                  background: transparent;
                  font-size: 11px;
                  font-weight: 800;
                  font-family: inherit;
                  letter-spacing: 0.05em;
                  text-align: left;
                  text-transform: uppercase;
                  color: #425365;
                  cursor: pointer;
                  display: flex;
                  align-items: center;
                  gap: 8px;
                }
                .catnip-var-group-title:hover {
                  color: #2f4357;
                }
                .catnip-var-group-title:focus-visible {
                  outline: 2px solid #1976d2;
                  outline-offset: 1px;
                }
                .catnip-var-group-chevron {
                  flex: 0 0 28px;
                  width: 28px;
                  height: 28px;
                  display: inline-flex;
                  align-items: center;
                  justify-content: center;
                  color: #425365;
                  font-family: Arial, Helvetica, sans-serif;
                  font-size: 16px;
                  line-height: 1;
                }
                .catnip-var-item {
                  margin-left: 12px;
                  margin-top: 2px;
                  padding: 7px 10px;
                  border-radius: 4px;
                  cursor: grab;
                  user-select: none;
                }
                .catnip-var-item:hover {
                  background: #eaf0f6;
                }
                .catnip-main-row {
                  flex-wrap: nowrap;
                }
                .catnip-main-row > .catnip-variable-column {
                  flex: 0 0 max(200px, 16.666667%);
                  width: max(200px, 16.666667%);
                  max-width: 50%;
                }
                .catnip-main-row > .catnip-content-column {
                  flex: 1 1 0;
                  width: auto;
                  max-width: none;
                  min-width: 0;
                }
                .catnip-variable-resizer {
                  position: relative;
                  align-self: stretch;
                  flex: 0 0 2px;
                  z-index: 5;
                  width: 2px;
                  min-width: 2px;
                  min-height: 80vh;
                  background: #aeb8c2;
                  cursor: col-resize;
                  touch-action: none;
                  outline: none;
                  user-select: none;
                  transition: background 0.15s;
                }
                .catnip-variable-resizer::before {
                  content: "";
                  position: absolute;
                  top: 0;
                  right: -3px;
                  bottom: 0;
                  left: -3px;
                  cursor: col-resize;
                }
                .catnip-variable-resizer:hover,
                .catnip-variable-resizer:focus-visible,
                .catnip-variable-resizer-active {
                  background: #1976d2;
                }
                .catnip-variable-panel-resizing {
                  cursor: col-resize;
                  user-select: none;
                }
                .catnip-dropcell { transition: background 0.15s, outline-color 0.15s; }
                .catnip-timeline-driver-btn {
                  flex: 0 0 auto;
                  width: 24px;
                  height: 20px;
                  padding: 0;
                  display: inline-flex;
                  align-items: center;
                  justify-content: center;
                  border: 1px solid rgba(0, 0, 0, 0.35);
                  border-radius: 3px;
                  background: rgba(255, 255, 255, 0.9);
                  color: #222;
                  font-size: 11px;
                  font-family: Menlo, Consolas, monospace;
                  font-weight: 700;
                  line-height: 18px;
                  cursor: pointer;
                }
                .catnip-timeline-driver-btn[aria-pressed="true"] {
                  background: #263238;
                  border-color: #263238;
                  color: #fff;
                }
                .catnip-timeline-clock-icon {
                  position: relative;
                  display: block;
                  width: 13px;
                  height: 13px;
                  border: 2px solid currentColor;
                  border-radius: 50%;
                  box-sizing: border-box;
                }
                .catnip-timeline-clock-icon::before,
                .catnip-timeline-clock-icon::after {
                  content: "";
                  position: absolute;
                  left: 50%;
                  top: 50%;
                  width: 2px;
                  background: currentColor;
                  border-radius: 1px;
                  transform-origin: 50% 0;
                }
                .catnip-timeline-clock-icon::before {
                  height: 4px;
                  transform: translate(-50%, -1px) rotate(0deg);
                }
                .catnip-timeline-clock-icon::after {
                  height: 5px;
                  transform: translate(-50%, -1px) rotate(90deg);
                }
                .catnip-plot1d {
                  position: relative;
                  overflow: hidden;
                  touch-action: none;
                }
                .catnip-plot1d.is-panning {
                  cursor: grabbing;
                }
                .catnip-plot1d.is-zooming {
                  cursor: ns-resize;
                }
                body.catnip-plot-panning,
                body.catnip-plot-zooming {
                  user-select: none;
                }
                .catnip-plot1d svg {
                  font-family: Arial, Helvetica, sans-serif;
                }
                .catnip-plot-hover-tip {
                  position: absolute;
                  z-index: 5;
                  max-width: 180px;
                  padding: 4px 6px;
                  background: rgba(255, 255, 255, 0.92);
                  border: 1px solid #1565c0;
                  border-radius: 3px;
                  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
                  color: #111;
                  font-size: 11px;
                  line-height: 1.25;
                  white-space: pre;
                  pointer-events: none;
                }
                .catnip-plot-legend {
                  position: absolute;
                  top: 6px;
                  right: 6px;
                  z-index: 3;
                  display: flex;
                  flex-direction: column;
                  align-items: stretch;
                  gap: 2px;
                  max-width: min(48%, 160px);
                  max-height: 42%;
                  padding: 4px 6px;
                  background: rgba(255, 255, 255, 0.78);
                  border: 1px solid rgba(0, 0, 0, 0.18);
                  border-radius: 3px;
                  overflow: hidden;
                  box-sizing: border-box;
                  pointer-events: none;
                }
                .catnip-plot-legend-item {
                  display: flex;
                  align-items: center;
                  min-width: 0;
                  max-width: 100%;
                  gap: 4px;
                  font-size: 10px;
                  line-height: 1.1;
                  color: #222;
                }
                .catnip-plot-legend-line {
                  flex: 0 0 20px;
                  width: 20px;
                  height: 2px;
                  border-radius: 1px;
                  background: var(--catnip-legend-color, #1565c0);
                }
                .catnip-plot-legend-line[data-line-style="dash"] {
                  background: repeating-linear-gradient(to right, var(--catnip-legend-color, #1565c0) 0 8px, transparent 8px 12px);
                }
                .catnip-plot-legend-line[data-line-style="dot"] {
                  background: radial-gradient(circle at center, var(--catnip-legend-color, #1565c0) 0 1.6px, transparent 1.8px);
                  background-position: left center;
                  background-repeat: repeat-x;
                  background-size: 6px 3px;
                }
                .catnip-plot-legend-line[data-line-style="dash-dot"] {
                  background: repeating-linear-gradient(to right, var(--catnip-legend-color, #1565c0) 0 8px, transparent 8px 11px, var(--catnip-legend-color, #1565c0) 11px 13px, transparent 13px 17px);
                }
                .catnip-plot-legend-label {
                  min-width: 0;
                  max-width: 120px;
                  overflow: hidden;
                  text-overflow: ellipsis;
                  white-space: nowrap;
                }
                .catnip-scalar-field-view {
                  display: flex;
                  align-items: stretch;
                  justify-content: center;
                  gap: 6px;
                  width: 100%;
                  height: 100%;
                  min-width: 0;
                  min-height: 0;
                  padding: 6px;
                  box-sizing: border-box;
                  background: #111;
                }
                .catnip-scalar-field-plot-frame {
                  position: relative;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  flex: 1 1 auto;
                  min-width: 0;
                  min-height: 0;
                  overflow: hidden;
                }
                .catnip-scalar-field-plot-frame.catnip-scalar-field-show-axes {
                  padding-left: 16px;
                  padding-bottom: 14px;
                }
                .catnip-scalar-field-plot-frame.catnip-scalar-field-show-axes::before {
                  content: "";
                  position: absolute;
                  left: 10px;
                  top: 4px;
                  bottom: 12px;
                  width: 0;
                  border-left: 1px solid rgba(255, 255, 255, 0.78);
                  pointer-events: none;
                }
                .catnip-scalar-field-plot-frame.catnip-scalar-field-show-axes::after {
                  content: "";
                  position: absolute;
                  left: 10px;
                  right: 2px;
                  bottom: 12px;
                  height: 0;
                  border-bottom: 1px solid rgba(255, 255, 255, 0.78);
                  pointer-events: none;
                }
                .catnip-scalar-field-plot-frame img {
                  display: block;
                  width: 100%;
                  height: 100%;
                  min-width: 0;
                  min-height: 0;
                  object-fit: contain;
                  background: #111;
                }
                .catnip-scalar-field-colorbar {
                  display: flex;
                  align-items: stretch;
                  flex: 0 0 54px;
                  min-height: 0;
                  gap: 4px;
                  color: #fff;
                  font-size: 10px;
                  line-height: 1;
                  text-shadow: 0 1px 1px rgba(0, 0, 0, 0.55);
                }
                .catnip-scalar-field-colorbar-ramp {
                  flex: 0 0 14px;
                  width: 14px;
                  min-height: 32px;
                  border: 1px solid rgba(255, 255, 255, 0.72);
                  border-radius: 2px;
                  box-sizing: border-box;
                  background: var(--catnip-scalar-field-colorbar, linear-gradient(to top, #440154, #fde725));
                }
                .catnip-scalar-field-colorbar-labels {
                  display: flex;
                  flex-direction: column;
                  justify-content: space-between;
                  align-items: flex-start;
                  min-width: 0;
                  max-width: 36px;
                  overflow: hidden;
                }
                .catnip-scalar-field-colorbar-label {
                  max-width: 36px;
                  overflow: hidden;
                  text-overflow: ellipsis;
                  white-space: nowrap;
                }
                .catnip-drop-hover {
                  background: #e3f2fd !important;
                  box-shadow: inset 0 0 0 2px #1976d2 !important;
                }
                .catnip-main-grid {
                  position: relative;
                }
                .catnip-grid-track-resize-handle {
                  position: absolute;
                  z-index: 6;
                  opacity: 0;
                  background: rgba(21, 101, 192, 0.3);
                  transition: opacity 0.12s ease, background 0.12s ease;
                }
                .catnip-dropcell:hover > .catnip-grid-track-resize-handle,
                .catnip-grid-track-resize-handle.active,
                .catnip-main-grid.is-resizing .catnip-grid-track-resize-handle {
                  opacity: 1;
                }
                .catnip-grid-track-resize-handle:hover,
                .catnip-grid-track-resize-handle.active {
                  background: rgba(21, 101, 192, 0.65);
                }
                .catnip-grid-col-resize-handle {
                  top: 32px;
                  right: 0;
                  bottom: 0;
                  width: 8px;
                  cursor: col-resize;
                }
                .catnip-grid-left-resize-handle {
                  left: 0;
                  right: auto;
                }
                .catnip-grid-row-resize-handle {
                  left: 0;
                  right: 0;
                  bottom: 0;
                  height: 8px;
                  cursor: row-resize;
                }
                .catnip-grid-top-resize-handle {
                  top: 0;
                  bottom: auto;
                }
                .catnip-grid-corner-resize-handle {
                  width: 12px;
                  height: 12px;
                  z-index: 7;
                }
                .catnip-grid-corner-bottom-left {
                  left: 0;
                  bottom: 0;
                  cursor: nesw-resize;
                }
                .catnip-grid-corner-bottom-right {
                  right: 0;
                  bottom: 0;
                  cursor: nwse-resize;
                }
                body.catnip-grid-col-resizing,
                body.catnip-grid-col-resizing * {
                  cursor: col-resize !important;
                  user-select: none !important;
                }
                body.catnip-grid-row-resizing,
                body.catnip-grid-row-resizing * {
                  cursor: row-resize !important;
                  user-select: none !important;
                }
                body.catnip-grid-corner-nwse-resizing,
                body.catnip-grid-corner-nwse-resizing * {
                  cursor: nwse-resize !important;
                  user-select: none !important;
                }
                body.catnip-grid-corner-nesw-resizing,
                body.catnip-grid-corner-nesw-resizing * {
                  cursor: nesw-resize !important;
                  user-select: none !important;
                }
                .catnip-panzoom-viewport {
                  width: 100%;
                  height: 100%;
                  min-width: 0;
                  min-height: 0;
                  position: relative;
                  overflow: hidden;
                  background: #111;
                  touch-action: none;
                }
                .catnip-panzoom-content {
                  width: 100%;
                  height: 100%;
                  min-width: 0;
                  min-height: 0;
                  transform-origin: 0 0;
                  will-change: transform;
                }
                .catnip-panzoom-viewport.is-panzoomed .catnip-panzoom-content {
                  cursor: grab;
                }
                .catnip-panzoom-viewport.is-panning .catnip-panzoom-content {
                  cursor: grabbing;
                }
                .catnip-panzoom-viewport.is-zooming .catnip-panzoom-content {
                  cursor: zoom-in;
                }
                body.catnip-panzoom-panning,
                body.catnip-panzoom-panning * {
                  cursor: grabbing !important;
                  user-select: none !important;
                }
                body.catnip-panzoom-zooming,
                body.catnip-panzoom-zooming * {
                  cursor: zoom-in !important;
                  user-select: none !important;
                }
                .catnip-empty-cell {
                  height: 100%;
                  display: flex;
                  flex-direction: column;
                  align-items: center;
                  justify-content: center;
                  gap: 6px;
                  color: #777;
                }
                .catnip-empty-plus {
                  color: #9a9a9a;
                  font-size: 26px;
                  font-weight: 300;
                  line-height: 1;
                }
                .catnip-empty-hover-label {
                  min-height: 14px;
                  color: #777;
                  font-size: 11px;
                  line-height: 14px;
                  opacity: 0;
                  transition: opacity 0.12s ease;
                }
                .catnip-dropcell:hover .catnip-empty-plus {
                  color: #555;
                }
                .catnip-dropcell:hover .catnip-empty-hover-label {
                  opacity: 1;
                }
                .catnip-vcr-bar {
                  display: flex;
                  align-items: center;
                  gap: 6px 8px;
                  flex-wrap: nowrap;
                  width: 100%;
                  min-height: 34px;
                  margin: 0;
                }
                .catnip-grid-controls-header {
                  flex: 0 0 auto;
                  padding: 4px 8px;
                  border-bottom: 1px solid #d8d8d8;
                  background: #fff;
                }
                .catnip-vcr-controls {
                  display: flex;
                  align-items: center;
                  gap: 3px;
                  flex: 0 0 auto;
                }
                .catnip-vcr-btn,
                .catnip-vcr-bar button[data-vcr-action],
                .catnip-grid-layout-btn,
                .catnip-toolbar-menu-btn {
                  min-width: 28px;
                  height: 24px;
                  border: 1px solid #9d9d9d;
                  border-radius: 3px;
                  background: #fff;
                  color: #222;
                  font-size: 12px;
                  line-height: 1;
                  cursor: pointer;
                  padding: 0 8px;
                }
                .catnip-vcr-btn {
                  width: 34px;
                  min-width: 34px;
                  padding: 0;
                  font-family: Menlo, Consolas, monospace;
                  font-weight: 600;
                  letter-spacing: 0;
                  white-space: nowrap;
                }
                .catnip-vcr-btn:hover,
                .catnip-vcr-bar button[data-vcr-action]:hover,
                .catnip-grid-layout-btn:hover:not(:disabled),
                .catnip-toolbar-menu-btn:hover:not(:disabled) {
                  background: #f2f2f2;
                }
                .catnip-vcr-btn:disabled,
                .catnip-vcr-bar button[data-vcr-action]:disabled,
                .catnip-grid-layout-btn:disabled,
                .catnip-toolbar-menu-btn:disabled {
                  opacity: 0.45;
                  cursor: not-allowed;
                }
                .catnip-vcr-time {
                  flex: 0 0 auto;
                  min-width: 114px;
                  text-align: center;
                }
                .catnip-vcr-slider {
                  flex: 1 1 260px;
                  min-width: 160px;
                  max-width: none;
                  cursor: pointer;
                }
                .catnip-grid-layout-controls {
                  flex: 0 0 auto;
                  margin-left: auto;
                  display: flex;
                  flex-direction: row;
                  align-items: center;
                  gap: 6px;
                }
                .catnip-toolbar-menu {
                  display: flex;
                  align-items: center;
                  position: relative;
                }
                .catnip-toolbar-menu-btn {
                  min-width: 68px;
                  white-space: nowrap;
                }
                .catnip-toolbar-icon-btn {
                  min-width: 28px;
                  width: 28px;
                  padding: 0;
                }
                .catnip-grid-layout-btn {
                  min-width: 28px;
                  padding: 0 6px;
                }
                .catnip-toolbar-popover-title {
                  color: #333;
                  font-size: 12px;
                  font-weight: 600;
                  margin-bottom: 8px;
                }
                .catnip-grid-sizing-mode {
                  display: grid;
                  grid-template-columns: 1fr 1fr;
                  gap: 4px;
                  margin-bottom: 10px;
                }
                .catnip-grid-sizing-mode-btn {
                  height: 26px;
                  border: 1px solid #9d9d9d;
                  border-radius: 3px;
                  background: #fff;
                  color: #222;
                  font-size: 12px;
                  cursor: pointer;
                }
                .catnip-grid-sizing-mode-btn.active {
                  background: #dbeafe;
                  border-color: #1976d2;
                  color: #0d47a1;
                  font-weight: 600;
                }
                .catnip-grid-sizing-section-label {
                  color: #555;
                  font-size: 11px;
                  line-height: 1;
                  margin-bottom: 6px;
                }
                .catnip-size-stepper {
                  display: flex;
                  align-items: center;
                  gap: 6px;
                  min-height: 28px;
                }
                .catnip-size-stepper-input {
                  width: 74px;
                  height: 26px;
                  border: 1px solid #9d9d9d;
                  border-radius: 3px;
                  padding: 0 5px;
                  font-size: 12px;
                  text-align: right;
                  box-sizing: border-box;
                }
                .catnip-size-stepper-unit {
                  color: #555;
                  font-size: 12px;
                  min-width: 16px;
                }
                .catnip-grid-reset-tracks-btn {
                  width: 100%;
                  margin-top: 8px;
                  min-height: 26px;
                  border: 1px solid #9d9d9d;
                  border-radius: 3px;
                  background: #fff;
                  color: #222;
                  font-size: 12px;
                  cursor: pointer;
                }
                .catnip-grid-reset-tracks-btn:hover {
                  background: #f2f2f2;
                }
                .catnip-grid-size-trigger {
                  width: 100%;
                  height: 28px;
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 8px;
                  border: 1px solid #9d9d9d;
                  border-radius: 3px;
                  background: #fff;
                  color: #222;
                  font-size: 12px;
                  padding: 0 8px;
                  cursor: pointer;
                }
                .catnip-grid-size-trigger:hover {
                  background: #f2f2f2;
                }
                .catnip-grid-size-trigger-label {
                  color: #333;
                  font-weight: 500;
                }
                .catnip-grid-size-trigger-value {
                  color: #111;
                  font-variant-numeric: tabular-nums;
                }
                .catnip-grid-size-popover {
                  width: 226px;
                }
                .catnip-settings-popover {
                  width: 300px;
                }
                .catnip-settings-section {
                  padding-top: 2px;
                }
                .catnip-settings-section + .catnip-settings-section {
                  margin-top: 12px;
                  padding-top: 10px;
                  border-top: 1px solid #e0e0e0;
                }
                .catnip-settings-section-title {
                  color: #333;
                  font-size: 12px;
                  font-weight: 600;
                  margin-bottom: 8px;
                }
                .catnip-settings-row {
                  display: grid;
                  grid-template-columns: minmax(0, 1fr) 104px;
                  align-items: center;
                  gap: 8px;
                }
                .catnip-grid-picker {
                  display: grid;
                  grid-template-columns: repeat(8, 18px);
                  gap: 3px;
                  margin-bottom: 8px;
                }
                .catnip-grid-picker-cell {
                  width: 18px;
                  height: 18px;
                  padding: 0;
                  border: 1px solid #9d9d9d;
                  border-radius: 2px;
                  background: #fff;
                  cursor: pointer;
                }
                .catnip-grid-picker-cell.selected {
                  background: #dbeafe;
                  border-color: #1976d2;
                }
                .catnip-grid-picker-cell.current {
                  box-shadow: inset 0 0 0 2px #0d47a1;
                }
                .catnip-grid-picker-label {
                  min-height: 16px;
                  margin-bottom: 8px;
                  color: #555;
                  text-align: center;
                }
                .catnip-grid-layout-stepper {
                  display: grid;
                  grid-template-columns: 44px 28px 28px 28px;
                  align-items: center;
                  gap: 6px;
                  margin-top: 4px;
                }
                .catnip-grid-layout-stepper-label {
                  color: #555;
                }
                .catnip-scalar-plot-policy {
                  height: 24px;
                  border: 1px solid #9d9d9d;
                  border-radius: 3px;
                  background: #fff;
                  color: #222;
                  font-size: 12px;
                  padding: 0 4px;
                }
                .catnip-scalar-plot-label {
                  white-space: nowrap;
                }
                .catnip-floating-options-panel {
                  position: fixed;
                  top: 84px;
                  left: max(8px, min(320px, calc(100vw - 568px)));
                  z-index: 9000;
                  width: min(560px, calc(100vw - 16px));
                  max-height: calc(100vh - 16px);
                }
                .catnip-floating-options-panel.catnip-plot-settings-panel {
                  left: max(8px, min(240px, calc(100vw - 768px)));
                  width: min(760px, calc(100vw - 16px));
                }
                .catnip-floating-options-panel.is-dragging {
                  user-select: none;
                }
                .catnip-floating-options-card {
                  max-height: inherit;
                  display: flex;
                  flex-direction: column;
                }
                .catnip-floating-options-titlebar {
                  min-height: 42px;
                  padding: 8px 12px !important;
                  border-bottom: 1px solid #dddddd;
                }
                .catnip-floating-panel-drag-handle {
                  min-width: 0;
                  flex: 1 1 auto;
                  cursor: move;
                  user-select: none;
                  white-space: nowrap;
                  overflow: hidden;
                  text-overflow: ellipsis;
                }
                .catnip-floating-options-content {
                  overflow: auto;
                  max-height: calc(100vh - 136px);
                }
                .catnip-plugin-options-list {
                  display: flex;
                  flex-direction: column;
                  gap: 10px;
                  min-width: 0;
                }
                .catnip-plugin-option-row {
                  display: grid;
                  grid-template-columns: minmax(120px, 180px) minmax(0, 1fr);
                  align-items: center;
                  gap: 8px 12px;
                  min-width: 0;
                }
                .catnip-plugin-option-label {
                  min-width: 0;
                  font-weight: 600;
                  line-height: 20px;
                  overflow: hidden;
                  text-overflow: ellipsis;
                }
                .catnip-plugin-option-control {
                  min-width: 0;
                  width: 100%;
                }
                .catnip-plugin-option-input {
                  width: 100%;
                  min-width: 0;
                  height: 26px;
                  border: 1px solid #9d9d9d;
                  border-radius: 3px;
                  background: #fff;
                  color: #222;
                  font-size: 12px;
                  padding: 0 6px;
                }
                .catnip-plugin-option-checkbox {
                  width: 14px;
                  height: 14px;
                  margin: 0;
                }
                .catnip-plugin-option-select {
                  width: min(180px, 100%);
                }
                @media (max-width: 560px) {
                  .catnip-plugin-option-row {
                    grid-template-columns: minmax(0, 1fr);
                    align-items: start;
                  }
                  .catnip-plugin-option-select {
                    width: 100%;
                  }
                }
                .catnip-plot-settings-axis-row.catnip-scalar-field-range-row {
                  display: flex;
                  align-items: center;
                  flex-wrap: wrap;
                  gap: 10px 12px;
                }
                .catnip-scalar-field-auto-control {
                  display: inline-flex;
                  align-items: center;
                  gap: 6px;
                  flex: 0 0 auto;
                  white-space: nowrap;
                  font-size: 14px;
                  line-height: 22px;
                }
                .catnip-scalar-field-auto-checkbox {
                  flex: 0 0 auto;
                  width: 14px;
                  height: 14px;
                  margin: 0;
                }
                .catnip-scalar-field-range-row .catnip-plot-settings-axis-label {
                  flex: 0 0 auto;
                  font-size: 14px;
                  line-height: 22px;
                  margin-left: 2px;
                }
                .catnip-scalar-field-range-row .catnip-plot-settings-axis-label.is-disabled {
                  opacity: 0.45;
                }
                .catnip-scalar-field-range-row .v-input {
                  flex: 0 0 120px;
                  min-width: 120px;
                  max-width: 120px;
                }
                .catnip-scalar-field-display-options {
                  display: flex;
                  align-items: center;
                  flex-wrap: wrap;
                  gap: 10px 18px;
                }
                .catnip-scalar-field-colormap {
                  min-width: 180px;
                }
                .catnip-plot-settings-axis-list {
                  display: flex;
                  flex-direction: column;
                  gap: 6px;
                }
                .catnip-plot-settings-section {
                  border: 1px solid #d8d8d8;
                  border-radius: 4px;
                  padding: 8px;
                }
                .catnip-plot-settings-section-title {
                  font-weight: 600;
                  margin-bottom: 6px;
                }
                .catnip-plot-settings-axis-row {
                  display: grid;
                  grid-template-columns: 24px 120px minmax(90px, 1fr) minmax(90px, 1fr) auto 96px;
                  align-items: center;
                  gap: 8px;
                }
                .catnip-plot-settings-axis-label {
                  font-weight: 600;
                  white-space: nowrap;
                }
                .catnip-plot-settings-row {
                  display: flex;
                  align-items: center;
                  gap: 8px;
                  margin-top: 6px;
                }
                .catnip-plot-settings-grid-controls {
                  display: flex;
                  align-items: center;
                  flex-wrap: wrap;
                  gap: 10px 14px;
                }
                .catnip-plot-settings-background-control {
                  display: flex;
                  align-items: center;
                  gap: 6px;
                }
                .catnip-plot-settings-toggle {
                  flex: 0 0 auto;
                }
                .catnip-plot-settings-toggle .v-selection-control {
                  min-height: 24px;
                }
                .catnip-plot-settings-toggle .v-selection-control__wrapper {
                  margin-inline-end: 0;
                }
                .catnip-plot-settings-curves-layout {
                  display: grid;
                  grid-template-columns: minmax(240px, 0.9fr) minmax(220px, 1.1fr);
                  align-items: start;
                  gap: 12px;
                }
                .catnip-plot-settings-curve-controls {
                  display: flex;
                  align-items: center;
                  flex-wrap: wrap;
                  gap: 8px;
                }
                .catnip-plot-settings-color-list {
                  min-width: 0;
                }
                .catnip-plot-settings-series-row {
                  display: grid;
                  grid-template-columns: 32px minmax(0, 1fr) 92px;
                  align-items: center;
                  gap: 6px 8px;
                  padding: 4px 0;
                  border-bottom: 1px solid #eeeeee;
                }
                .catnip-plot-settings-series-row:last-child {
                  border-bottom: 0;
                  padding-bottom: 0;
                }
                .catnip-plot-settings-series-label {
                  min-width: 0;
                  white-space: nowrap;
                  overflow: hidden;
                  text-overflow: ellipsis;
                }
                .catnip-plot-settings-line-style {
                  width: 92px;
                  height: 24px;
                  border: 1px solid #9d9d9d;
                  border-radius: 3px;
                  background: #fff;
                  color: #222;
                  font-size: 12px;
                  padding: 0 4px;
                }
                .catnip-plot-settings-color-menu {
                  width: 24px;
                  height: 24px;
                  justify-self: start;
                }
                .catnip-plot-settings-current-color {
                  width: 24px;
                  height: 24px;
                  border: 1px solid rgba(0, 0, 0, 0.35);
                  border-radius: 3px;
                  padding: 0;
                  cursor: pointer;
                  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.45);
                }
                .catnip-plot-settings-color-popup {
                  width: 238px;
                }
                .catnip-plot-settings-popup-title {
                  font-weight: 600;
                  color: #333;
                  margin-bottom: 6px;
                }
                .catnip-plot-settings-standard-colors {
                  display: flex;
                  flex-wrap: wrap;
                  align-items: center;
                  gap: 3px;
                  padding-bottom: 8px;
                  border-bottom: 1px solid #e4e4e4;
                  margin-bottom: 8px;
                }
                .catnip-plot-settings-color-swatch {
                  width: 16px;
                  height: 16px;
                  border: 1px solid rgba(0, 0, 0, 0.25);
                  border-radius: 0;
                  padding: 0;
                  cursor: pointer;
                }
                .catnip-plot-settings-more-colors {
                  font-weight: 600;
                  color: #333;
                  margin-bottom: 4px;
                }
                #catnip-context-menu {
                  background: #fff;
                  border: 1px solid #c9c9c9;
                  border-radius: 4px;
                  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.2);
                  min-width: 170px;
                  padding: 4px 0;
                }
                #catnip-context-menu .menu-item {
                  padding: 7px 12px;
                  cursor: pointer;
                  font-size: 13px;
                  line-height: 1.2;
                  user-select: none;
                }
                #catnip-context-menu .menu-item:hover {
                  background: #e3f2fd;
                }
                #catnip-context-menu .menu-item.danger:hover {
                  background: #ffebee;
                  color: #c62828;
                }
                #catnip-context-menu .menu-submenu {
                  position: relative;
                }
                #catnip-context-menu .menu-submenu-trigger {
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 16px;
                }
                #catnip-context-menu .menu-submenu-arrow {
                  color: #666;
                  font-size: 11px;
                }
                #catnip-context-menu .menu-submenu-panel {
                  display: none;
                  position: absolute;
                  top: -5px;
                  left: 100%;
                  min-width: 150px;
                  padding: 4px 0;
                  background: #fff;
                  border: 1px solid #c9c9c9;
                  border-radius: 4px;
                  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.2);
                }
                #catnip-context-menu .menu-submenu:hover .menu-submenu-panel {
                  display: block;
                }
                #catnip-context-menu .menu-section {
                  padding: 6px 12px 4px;
                  font-size: 11px;
                  color: #666;
                  border-top: 1px solid #ececec;
                  margin-top: 4px;
                }
                #catnip-context-menu .menu-label {
                  padding: 6px 12px 4px;
                  font-size: 11px;
                  color: #666;
                  border-bottom: 1px solid #ececec;
                  margin-bottom: 4px;
                  white-space: nowrap;
                  overflow: hidden;
                  text-overflow: ellipsis;
                }
                """
            )
            with vuetify.VDialog(v_model=("showHelpModal",), max_width="520"):
                with vuetify.VCard():
                    with vuetify.VCardTitle():
                        with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                            html.Div("{{ helpModalTitle || 'Help' }}")
                            vuetify.VSpacer()
                            vuetify.VBtn("Close", variant="text", size="small", click=ctrl.close_help_modal)
                    with vuetify.VCardText():
                        vuetify.VTextarea(
                            v_model=("helpModalText",),
                            readonly=True,
                            auto_grow=True,
                            rows=3,
                            variant="outlined",
                            hide_details=True,
                        )
            with vuetify.VContainer(fluid=True, class_="pa-2"):
                html.Div(
                    "",
                    id="catnip-reset-view-request",
                    style="display:none;",
                    raw_attrs=[':data-reset-view-request="JSON.stringify(resetViewRequest || {})"'],
                )
                with vuetify.VRow(classes="catnip-main-row", no_gutters=True):
                    with vuetify.VCol(
                        id="catnip-variable-column",
                        classes="catnip-variable-column",
                        style="display:flex; flex-direction:column; height:80vh;",
                    ):
                        with vuetify.VCard(
                            variant="outlined",
                            style="flex:1 1 auto; min-height:0; display:flex; flex-direction:column;",
                        ):
                            with vuetify.VCardTitle():
                                html.Div("Variables")
                            with vuetify.VCardText(style="flex:1 1 auto; min-height:0; overflow-y:auto;"):
                                with html.Div(
                                    style="display:flex; align-items:center; gap:8px; padding:0 4px 8px 4px;",
                                ):
                                    html.Span("Group by:", class_="text-caption")
                                    with vuetify.VBtnToggle(
                                        v_model=("variablePaneView",),
                                        mandatory=True,
                                        density="compact",
                                        divided=True,
                                        variant="outlined",
                                    ):
                                        vuetify.VBtn("Variable", value="variables", size="small")
                                        vuetify.VBtn("File", value="files", size="small")
                                with html.Div(style="padding:0 4px 8px 4px;"):
                                    vuetify.VCheckbox(
                                        v_model=("showOnlyVisualizedVars",),
                                        label="Only with visualizations",
                                        density="compact",
                                        hide_details=True,
                                    )
                                with vuetify.VList(density="compact", class_="catnip-var-list"):
                                    html.Div(
                                        "No variables",
                                        v_if="!(variableGroups || []).length",
                                        class_="text-caption",
                                        style="padding:8px 10px; color:#777;",
                                    )
                                    with vuetify.Template(v_for="group in variableGroups", key="group.name"):
                                        with html.Div(
                                            class_="catnip-var-group",
                                            style=(
                                                "border:1px solid #b8c4d1;"
                                                "background:#f4f7fa;"
                                                "box-shadow: inset 0 0 0 1px #e2e8ef;"
                                            ),
                                        ):
                                            with html.Button(
                                                class_="catnip-var-group-title",
                                                click=(ctrl.toggle_variable_group, "[group.name]"),
                                                style="font-weight:800;",
                                                raw_attrs=[
                                                    'type="button"',
                                                    ':aria-expanded="!(variableGroupCollapsed && variableGroupCollapsed[group.name])"',
                                                ],
                                            ):
                                                html.Span(
                                                    "{{ (variableGroupCollapsed && variableGroupCollapsed[group.name]) ? '▸' : '▾' }}",
                                                    class_="catnip-var-group-chevron",
                                                )
                                                html.Span(
                                                    "{{ group.name + (((group.file_count || 0) > 1) ? (' (' + group.file_count + ')') : '') }}",
                                                    raw_attrs=[':title="group.name"'],
                                                    style="flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;",
                                                )
                                            with html.Div(v_if="!(variableGroupCollapsed && variableGroupCollapsed[group.name])"):
                                                with vuetify.Template(v_for="v in group.variables", key="group.name + '::' + v.id"):
                                                    with html.Div(
                                                        click=(ctrl.pick_var, "[v.id]"),
                                                        draggable="true",
                                                        classes="catnip-draggable-var catnip-var-item",
                                                        raw_attrs=[':data-item="v.id"', ':title="v.path || v.id"'],
                                                        style=(
                                                            "((v.id === selectedVar) ? 'background:#dfe7ef; box-shadow: inset 0 0 0 1px #b9c8d7;' : '')",
                                                        ),
                                                    ):
                                                        html.Span("{{ v.label || v.name || v.id }}")

                    html.Div(
                        classes="catnip-variable-resizer",
                        raw_attrs=[
                            "data-variable-panel-resizer",
                            'role="separator"',
                            'aria-label="Resize variable list"',
                            'aria-orientation="vertical"',
                            'aria-valuemin="180"',
                            'tabindex="0"',
                        ],
                        title="Drag to resize the variable list",
                    )

                    with vuetify.VCol(
                        classes="catnip-content-column",
                        style="display:flex; flex-direction:column; height:80vh;",
                    ):
                        with vuetify.VCard(
                            variant="outlined",
                            style="flex:1 1 auto; min-height:0; display:flex; flex-direction:column;",
                        ):
                            with vuetify.VCardText(
                                style=(
                                    "height:100%;"
                                    "min-height:0;"
                                    "display:flex;"
                                    "flex-direction:column;"
                                    "overflow:hidden;"
                                ),
                            ):
                                with html.Div(classes="catnip-vcr-bar catnip-grid-controls-header"):
                                    with html.Div(classes="catnip-vcr-controls"):
                                        html.Button(
                                            "|<",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="start"',
                                            ],
                                            title="Jump to start",
                                        )
                                        html.Button(
                                            "<<",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="back"',
                                            ],
                                            title="Back step",
                                        )
                                        html.Button(
                                            "▶",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="play"',
                                            ],
                                            title="Play all",
                                        )
                                        html.Button(
                                            "⏸",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="pause"',
                                            ],
                                            title="Pause all",
                                        )
                                        html.Button(
                                            ">>",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="forward"',
                                            ],
                                            title="Forward step",
                                        )
                                        html.Button(
                                            ">|",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="end"',
                                            ],
                                            title="Jump to end",
                                        )
                                    html.Span(
                                        "Time = 0.000000",
                                        id="catnip-vcr-time-value",
                                        class_="text-caption catnip-vcr-time",
                                    )
                                    html.Input(
                                        type="range",
                                        id="catnip-vcr-step-slider",
                                        classes="catnip-vcr-slider",
                                        raw_attrs=[
                                            'min="0"',
                                            'max="20"',
                                            'step="1"',
                                            'value="0"',
                                            'aria-label="Timestep"',
                                            'title="Timestep (frame index)"',
                                        ],
                                    )
                                    _build_grid_layout_controls(ctrl)
                                with vuetify.Template(v_if="scalarPlotStatus"):
                                    html.Div("{{ scalarPlotStatus }}", class_="text-caption mb-2", style="color:#8a4b00;")
                                with html.Div(
                                    classes="catnip-main-grid",
                                    raw_attrs=[
                                        ':data-grid-sizing-mode="gridSizingMode"',
                                        ':data-grid-cols="gridCols"',
                                        ':data-grid-rows="gridRows"',
                                        ':data-grid-column-sizes="(gridColumnSizes || []).join(\',\')"',
                                        ':data-grid-row-sizes="(gridRowSizes || []).join(\',\')"',
                                        ':data-grid-column-weights="(gridColumnWeights || []).join(\',\')"',
                                        ':data-grid-row-weights="(gridRowWeights || []).join(\',\')"',
                                        ':data-grid-min-column-size="gridMinCellSize"',
                                        ':data-grid-max-column-size="gridMaxCellSize"',
                                        ':data-grid-min-row-size="Number(gridMinCellSize || 80) + 32"',
                                        ':data-grid-max-row-size="Number(gridMaxCellSize || 5000) + 32"',
                                        ':data-grid-fit-min-column-size="gridFitMinCellSize"',
                                        ':data-grid-fit-min-row-size="Number(gridFitMinCellSize || 180) + 32"',
                                        ':data-grid-column-fallback="gridCellSize"',
                                        ':data-grid-row-fallback="Number(gridCellSize || 300) + 32"',
                                    ],
                                    style=(
                                        "('display:grid;'"
                                        " + ((gridSizingMode === 'fit')"
                                        " ? ('grid-template-columns:' + String(gridFitColumnTemplate || ('repeat(' + gridCols + ', minmax(' + Number(gridFitMinCellSize || 180) + 'px, 1fr))')) + ';'"
                                        " + 'grid-template-rows:' + String(gridFitRowTemplate || ('repeat(' + gridRows + ', minmax(' + (Number(gridFitMinCellSize || 180) + 32) + 'px, 1fr))')) + ';'"
                                        " + 'justify-content:stretch;'"
                                        " + 'align-content:stretch;')"
                                        " : ('grid-template-columns:' + String(gridColumnTemplate || ('repeat(' + gridCols + ', ' + Number(gridCellSize || 300) + 'px)')) + ';'"
                                        " + 'grid-template-rows:' + String(gridRowTemplate || ('repeat(' + gridRows + ', ' + (Number(gridCellSize || 300) + 32) + 'px)')) + ';'"
                                        " + 'justify-content:center;'"
                                        " + 'align-content:start;'))"
                                        " + 'flex:1 1 auto;'"
                                        " + 'min-height:0;'"
                                        " + 'overflow:auto;'"
                                        " + 'width:100%;'"
                                        " + 'box-sizing:border-box;'"
                                        " + 'margin:4px 0 0 0;'"
                                        " + 'border:1px solid #cfcfcf;')",
                                    ),
                                ):
                                    with vuetify.Template(v_for="(tile, i) in gridCells", key="i"):
                                        with html.Div(
                                            click=(
                                                ctrl.set_active_grid_cell,
                                                "[i, (($event && $event.target && $event.target.closest && $event.target.closest('.catnip-cell-close, .catnip-timeline-driver-btn, .catnip-grid-track-resize-handle')) ? 1 : 0), (($event && $event.shiftKey) ? 1 : 0)]",
                                            ),
                                            classes="catnip-dropcell",
                                            raw_attrs=[
                                                ':data-cell-index="i"',
                                                ':data-cell-filled="((tile && tile.variable_name) ? 1 : 0)"',
                                                ':data-timeline-driver="(timelineDriverCell === i ? 1 : 0)"',
                                                ':draggable="!!(tile && tile.variable_name)"',
                                            ],
                                            style=(
                                                "((gridLayoutMode === 'spanning')"
                                                " ? ('grid-row:' + Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + ' / span ' + Number((tile && tile.row_span) || 1) + ';grid-column:' + Number((tile && tile.grid_col) || ((i % gridCols) + 1)) + ' / span ' + Number((tile && tile.col_span) || 1) + ';')"
                                                " : '')"
                                                " + ((gridLayoutMode === 'spanning')"
                                                " ? 'width:100%; height:100%; min-width:0; min-height:0;'"
                                                " : ((gridSizingMode === 'fit')"
                                                " ? ('width:100%; height:100%; min-width:' + Number(gridFitMinCellSize || 180) + 'px; min-height:' + (Number(gridFitMinCellSize || 180) + 32) + 'px;')"
                                                " : 'width:100%; height:100%; min-width:0; min-height:0;'))"
                                                " + 'overflow:hidden; cursor:pointer; display:flex; flex-direction:column; position:relative; box-sizing:border-box;'"
                                                " + ((gridLayoutMode === 'spanning') ? 'border:1px solid #cfcfcf;' : ('border-left:1px solid #cfcfcf; border-top:1px solid #cfcfcf;'"
                                                " + (((i % gridCols) === (gridCols - 1)) ? 'border-right:1px solid #cfcfcf;' : '')"
                                                " + ((i >= ((gridRows - 1) * gridCols)) ? 'border-bottom:1px solid #cfcfcf;' : '')))"
                                                " + ((activeGridCell === i) ? 'background:#e7f0ff; outline:3px solid #0d47a1; outline-offset:-3px; z-index:2;' : '')"
                                                " + ((gridLayoutMode === 'spanning' && tile && tile.grid_hidden) ? 'display:none;' : '')",
                                            ),
                                        ):
                                            html.Div(
                                                classes="catnip-grid-track-resize-handle catnip-grid-col-resize-handle catnip-grid-left-resize-handle",
                                                v_if=(
                                                    "gridSizingMode !== 'fit'"
                                                    " && !(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                                    " && ((gridLayoutMode === 'spanning'"
                                                    " ? Number((tile && tile.grid_col) || ((i % gridCols) + 1))"
                                                    " : ((i % gridCols) + 1)) === 1)"
                                                ),
                                                raw_attrs=[
                                                    'role="separator"',
                                                    'aria-orientation="vertical"',
                                                    'title="Drag to resize column"',
                                                    'data-resize-edge="left"',
                                                    'data-col-index="0"',
                                                ],
                                            )
                                            html.Div(
                                                classes="catnip-grid-track-resize-handle catnip-grid-col-resize-handle",
                                                v_if=(
                                                    "!(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                                    " && (gridSizingMode !== 'fit' || ((gridLayoutMode === 'spanning'"
                                                    " ? (Number((tile && tile.grid_col) || ((i % gridCols) + 1)) + Number((tile && tile.col_span) || 1) - 1)"
                                                    " : ((i % gridCols) + 1)) < Number(gridCols || 0)))"
                                                ),
                                                raw_attrs=[
                                                    'role="separator"',
                                                    'aria-orientation="vertical"',
                                                    'title="Drag to resize column"',
                                                    'data-resize-edge="right"',
                                                    ':data-col-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_col) || ((i % gridCols) + 1)) + Number((tile && tile.col_span) || 1) - 2) : (i % gridCols)"',
                                                ],
                                            )
                                            html.Div(
                                                classes="catnip-grid-track-resize-handle catnip-grid-row-resize-handle catnip-grid-top-resize-handle",
                                                v_if=(
                                                    "gridSizingMode !== 'fit'"
                                                    " && !(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                                    " && ((gridLayoutMode === 'spanning'"
                                                    " ? Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1))"
                                                    " : (Math.floor(i / gridCols) + 1)) === 1)"
                                                ),
                                                raw_attrs=[
                                                    'role="separator"',
                                                    'aria-orientation="horizontal"',
                                                    'title="Drag to resize row"',
                                                    'data-resize-edge="top"',
                                                    'data-row-index="0"',
                                                ],
                                            )
                                            html.Div(
                                                classes="catnip-grid-track-resize-handle catnip-grid-row-resize-handle",
                                                v_if=(
                                                    "!(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                                    " && (gridSizingMode !== 'fit' || ((gridLayoutMode === 'spanning'"
                                                    " ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 1)"
                                                    " : (Math.floor(i / gridCols) + 1)) < Number(gridRows || 0)))"
                                                ),
                                                raw_attrs=[
                                                    'role="separator"',
                                                    'aria-orientation="horizontal"',
                                                    'title="Drag to resize row"',
                                                    'data-resize-edge="bottom"',
                                                    ':data-row-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 2) : Math.floor(i / gridCols)"',
                                                ],
                                            )
                                            html.Div(
                                                classes="catnip-grid-track-resize-handle catnip-grid-corner-resize-handle catnip-grid-corner-bottom-left",
                                                v_if=(
                                                    "!(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                                    " && (gridSizingMode !== 'fit' || ("
                                                    "((gridLayoutMode === 'spanning' ? Number((tile && tile.grid_col) || ((i % gridCols) + 1)) : ((i % gridCols) + 1)) > 1)"
                                                    " && ((gridLayoutMode === 'spanning' ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 1) : (Math.floor(i / gridCols) + 1)) < Number(gridRows || 0))"
                                                    "))"
                                                ),
                                                raw_attrs=[
                                                    'role="separator"',
                                                    'aria-orientation="vertical"',
                                                    'title="Drag to resize row and column"',
                                                    'data-col-edge="left"',
                                                    'data-row-edge="bottom"',
                                                    ':data-col-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_col) || ((i % gridCols) + 1)) - 1) : (i % gridCols)"',
                                                    ':data-row-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 2) : Math.floor(i / gridCols)"',
                                                ],
                                            )
                                            html.Div(
                                                classes="catnip-grid-track-resize-handle catnip-grid-corner-resize-handle catnip-grid-corner-bottom-right",
                                                v_if=(
                                                    "!(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                                    " && (gridSizingMode !== 'fit' || ("
                                                    "((gridLayoutMode === 'spanning' ? (Number((tile && tile.grid_col) || ((i % gridCols) + 1)) + Number((tile && tile.col_span) || 1) - 1) : ((i % gridCols) + 1)) < Number(gridCols || 0))"
                                                    " && ((gridLayoutMode === 'spanning' ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 1) : (Math.floor(i / gridCols) + 1)) < Number(gridRows || 0))"
                                                    "))"
                                                ),
                                                raw_attrs=[
                                                    'role="separator"',
                                                    'aria-orientation="vertical"',
                                                    'title="Drag to resize row and column"',
                                                    'data-col-edge="right"',
                                                    'data-row-edge="bottom"',
                                                    ':data-col-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_col) || ((i % gridCols) + 1)) + Number((tile && tile.col_span) || 1) - 2) : (i % gridCols)"',
                                                    ':data-row-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 2) : Math.floor(i / gridCols)"',
                                                ],
                                            )
                                            with vuetify.Template(v_if="tile && tile.variable_name"):
                                                with html.Div(
                                                    style=(
                                                        "'display:flex;'"
                                                        " + 'align-items:center;'"
                                                        " + 'gap:8px;'"
                                                        " + 'width:100%;'"
                                                        " + 'height:32px;'"
                                                        " + 'padding:4px 6px;'"
                                                        " + (((selectedGridCellMap || {})[String(i)]) ? 'background:#ef6c00; color:#fff; border-bottom:1px solid #b53d00;' : ((activeGridCell === i) ? 'background:#1565c0; color:#fff; border-bottom:1px solid #0d47a1;' : 'background:#7bd0ef; color:#111; border-bottom:1px solid #3ca7c9;'))",
                                                    ),
                                                ):
                                                    html.Div(
                                                        "{{ tile.display_title || tile.variable_name || 'variable' }}",
                                                        style="flex:1 1 auto; min-width:0; font-size:0.9rem; font-weight:400; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;",
                                                    )
                                                    with html.Button(
                                                        v_if=(
                                                            "(tile.time_values && tile.time_values.length)"
                                                            " || (tile.plot && tile.plot.series && tile.plot.series.length"
                                                            " && (String(tile.plot.x_label || '').toLowerCase() === 'time'"
                                                            " || String(tile.plot.x_label || '').toLowerCase() === 'physical time'))"
                                                        ),
                                                        classes="catnip-timeline-driver-btn",
                                                        click=(ctrl.toggle_timeline_driver_cell, "[i]"),
                                                        raw_attrs=[
                                                            'type="button"',
                                                            ':aria-pressed="timelineDriverCell === i ? \'true\' : \'false\'"',
                                                        ],
                                                        title="Use as timeline driver",
                                                    ):
                                                        html.Span(
                                                            classes="catnip-timeline-clock-icon",
                                                            raw_attrs=['aria-hidden="true"'],
                                                        )
                                                    html.Button(
                                                        "x",
                                                        classes="catnip-cell-close",
                                                        click=(ctrl.clear_grid_cell, "[i]"),
                                                        style=(
                                                            "margin-left:auto;"
                                                            "flex:0 0 auto;"
                                                            "width:18px;"
                                                            "height:18px;"
                                                            "line-height:16px;"
                                                            "padding:0;"
                                                            "font-size:11px;"
                                                            "border:1px solid #2c7c97;"
                                                            "border-radius:2px;"
                                                            "background:#fff;"
                                                            "color:#222;"
                                                            "cursor:pointer;"
                                                        ),
                                                        title="Remove",
                                                    )

                                                with html.Div(
                                                    style="width:100%; flex:1 1 auto; min-height:0; background:#111; position:relative; overflow:hidden;",
                                                ):
                                                    with vuetify.Template(v_if="tile.media_type === 'plot1d'"):
                                                        html.Div(
                                                            classes="catnip-plot1d",
                                                            raw_attrs=[
                                                                ':data-plot="JSON.stringify(tile.plot || {})"',
                                                                ':data-plot-settings="JSON.stringify(tile.plot_settings || {})"',
                                                            ],
                                                            style=(
                                                                "display:block;"
                                                                "width:100%;"
                                                                "height:100%;"
                                                                "background:#fff;"
                                                            ),
                                                        )
                                                        with vuetify.Template(
                                                            v_if=(
                                                                "tile.plot"
                                                                " && tile.plot.series"
                                                                " && tile.plot.series.length > 1"
                                                            ),
                                                        ):
                                                            with html.Div(classes="catnip-plot-legend"):
                                                                with vuetify.Template(
                                                                    v_for="(item, j) in ((tile.plot && tile.plot.series) || [])",
                                                                    key="j",
                                                                ):
                                                                    with html.Div(
                                                                        classes="catnip-plot-legend-item",
                                                                        raw_attrs=[
                                                                            ':title="item.source_label || item.source_key || (\'Series \' + (j + 1))"',
                                                                        ],
                                                                    ):
                                                                        html.Div(
                                                                            classes="catnip-plot-legend-line",
                                                                            raw_attrs=[
                                                                                ":data-line-style=\"(((tile.plot_settings && tile.plot_settings.series_styles && tile.plot_settings.series_styles[(item.source_key || item.source_label || ('series:' + j))] && tile.plot_settings.series_styles[(item.source_key || item.source_label || ('series:' + j))].line_style) || item.line_style || 'solid').toLowerCase().replace('_', '-'))\"",
                                                                                ":style=\"{'--catnip-legend-color': ((tile.plot_settings && tile.plot_settings.series_styles && tile.plot_settings.series_styles[(item.source_key || item.source_label || ('series:' + j))] && tile.plot_settings.series_styles[(item.source_key || item.source_label || ('series:' + j))].color) || (tile.plot_settings && tile.plot_settings.series_colors && tile.plot_settings.series_colors[(item.source_key || item.source_label || ('series:' + j))]) || item.color || '#1565c0')}\"",
                                                                            ],
                                                                        )
                                                                        html.Span(
                                                                            "{{ item.source_label || item.source_key || ('Series ' + (j + 1)) }}",
                                                                            classes="catnip-plot-legend-label",
                                                                        )
                                                    with vuetify.Template(v_if="tile.media_type !== 'plot1d'"):
                                                        with vuetify.Template(v_if="tile.src"):
                                                            with vuetify.Template(
                                                                v_if=(
                                                                    "(tile.media_type === 'image' || tile.media_type === 'image_sequence')"
                                                                    " && (tile.variable_type === 'scalarField'"
                                                                    " || tile.payload_type === 'SCALAR_FIELD'"
                                                                    " || tile.visualization_item_type === 'SCALAR_FIELD')"
                                                                )
                                                            ):
                                                                with html.Div(classes="catnip-scalar-field-view"):
                                                                    with html.Div(
                                                                        classes="catnip-scalar-field-plot-frame catnip-panzoom-viewport",
                                                                        raw_attrs=[
                                                                            ":class=\"{ 'catnip-scalar-field-show-axes': tile.scalar_field_settings && tile.scalar_field_settings.show_axes }\"",
                                                                        ],
                                                                    ):
                                                                        with html.Div(classes="catnip-panzoom-content"):
                                                                            with vuetify.Template(v_if="tile.media_type === 'image_sequence'"):
                                                                                html.Img(
                                                                                    src=("tile.src",),
                                                                                    class_="catnip-grid-image-sequence",
                                                                                    raw_attrs=[
                                                                                        'data-grid-image-sequence="1"',
                                                                                        ':data-fps="tile.fps || 2"',
                                                                                        ':data-frame-count="tile.frame_count || 0"',
                                                                                        ':data-frame-indices="(tile.frame_indices || []).join(\',\')"',
                                                                                        ':data-frame-sources="JSON.stringify(tile.frame_sources || [])"',
                                                                                        ':data-time-values="(tile.time_values || []).join(\',\')"',
                                                                                        ':data-time-mode="tile.time_mode || \'timestep\'"',
                                                                                        'data-current-frame="0"',
                                                                                        'draggable="false"',
                                                                                    ],
                                                                                )
                                                                            with vuetify.Template(v_if="tile.media_type === 'image'"):
                                                                                html.Img(src=("tile.src",), raw_attrs=['draggable="false"'])
                                                                    with vuetify.Template(
                                                                        v_if=(
                                                                            "tile.scalar_field_settings"
                                                                            " && tile.scalar_field_settings.show_colorbar"
                                                                        )
                                                                    ):
                                                                        with html.Div(classes="catnip-scalar-field-colorbar"):
                                                                            html.Div(
                                                                                classes="catnip-scalar-field-colorbar-ramp",
                                                                                raw_attrs=[
                                                                                    ":style=\"{ '--catnip-scalar-field-colorbar': ((tile.scalar_field_settings && tile.scalar_field_settings.colorbar_gradient) || 'linear-gradient(to top, #440154, #fde725)') }\"",
                                                                                ],
                                                                            )
                                                                            with html.Div(classes="catnip-scalar-field-colorbar-labels"):
                                                                                html.Div(
                                                                                    "{{ tile.scalar_field_colorbar_max || tile.max || '' }}",
                                                                                    classes="catnip-scalar-field-colorbar-label",
                                                                                    raw_attrs=[
                                                                                        ':title="String(tile.scalar_field_colorbar_max || tile.max || \'\')"',
                                                                                    ],
                                                                                )
                                                                                html.Div(
                                                                                    "{{ tile.scalar_field_colorbar_min || tile.min || '' }}",
                                                                                    classes="catnip-scalar-field-colorbar-label",
                                                                                    raw_attrs=[
                                                                                        ':title="String(tile.scalar_field_colorbar_min || tile.min || \'\')"',
                                                                                    ],
                                                                                )
                                                            with vuetify.Template(
                                                                v_if=(
                                                                    "tile.media_type === 'image_sequence'"
                                                                    " && !(tile.variable_type === 'scalarField'"
                                                                    " || tile.payload_type === 'SCALAR_FIELD'"
                                                                    " || tile.visualization_item_type === 'SCALAR_FIELD')"
                                                                )
                                                            ):
                                                                with html.Div(classes="catnip-panzoom-viewport"):
                                                                    with html.Div(classes="catnip-panzoom-content"):
                                                                        html.Img(
                                                                            src=("tile.src",),
                                                                            class_="catnip-grid-image-sequence",
                                                                            raw_attrs=[
                                                                                'data-grid-image-sequence="1"',
                                                                                ':data-fps="tile.fps || 2"',
                                                                                ':data-frame-count="tile.frame_count || 0"',
                                                                                ':data-frame-indices="(tile.frame_indices || []).join(\',\')"',
                                                                                ':data-frame-sources="JSON.stringify(tile.frame_sources || [])"',
                                                                                ':data-time-values="(tile.time_values || []).join(\',\')"',
                                                                                ':data-time-mode="tile.time_mode || \'timestep\'"',
                                                                                'data-current-frame="0"',
                                                                                'draggable="false"',
                                                                            ],
                                                                            style=(
                                                                                "display:block;"
                                                                                "width:100%;"
                                                                                "height:100%;"
                                                                                "object-fit:contain;"
                                                                                "background:#111;"
                                                                            ),
                                                                        )
                                                            with vuetify.Template(
                                                                v_if=(
                                                                    "tile.media_type === 'image'"
                                                                    " && !(tile.variable_type === 'scalarField'"
                                                                    " || tile.payload_type === 'SCALAR_FIELD'"
                                                                    " || tile.visualization_item_type === 'SCALAR_FIELD')"
                                                                )
                                                            ):
                                                                with html.Div(classes="catnip-panzoom-viewport"):
                                                                    with html.Div(classes="catnip-panzoom-content"):
                                                                        html.Img(
                                                                            src=("tile.src",),
                                                                            raw_attrs=['draggable="false"'],
                                                                            style=(
                                                                                "display:block;"
                                                                                "width:100%;"
                                                                                "height:100%;"
                                                                                "object-fit:contain;"
                                                                                "background:#111;"
                                                                            ),
                                                                        )
                                                            with vuetify.Template(v_if="tile.media_type !== 'image' && tile.media_type !== 'image_sequence'"):
                                                                with html.Div(classes="catnip-panzoom-viewport"):
                                                                    with html.Div(classes="catnip-panzoom-content"):
                                                                        html.Video(
                                                                            src=("tile.src",),
                                                                            class_="catnip-grid-video",
                                                                            controls=False,
                                                                            autoplay=False,
                                                                            loop=False,
                                                                            muted=True,
                                                                            raw_attrs=[
                                                                                'data-grid-video="1"',
                                                                                ':data-fps="tile.fps || 2"',
                                                                                ':data-frame-count="tile.frame_count || 0"',
                                                                                ':data-frame-indices="(tile.frame_indices || []).join(\',\')"',
                                                                                ':data-time-values="(tile.time_values || []).join(\',\')"',
                                                                                ':data-time-mode="tile.time_mode || \'timestep\'"',
                                                                                "playsinline",
                                                                                "webkit-playsinline",
                                                                            ],
                                                                            style=(
                                                                                "display:block;"
                                                                                "width:100%;"
                                                                                "height:100%;"
                                                                                "object-fit:contain;"
                                                                                "background:#111;"
                                                                            ),
                                                                        )
                                                        with vuetify.Template(v_if="!tile.src"):
                                                            html.Div(
                                                                "{{ tile.note ? tile.note : 'No movie src' }}",
                                                                class_="text-caption",
                                                                style=(
                                                                    "display:flex;"
                                                                    "height:100%;"
                                                                    "align-items:center;"
                                                                    "justify-content:center;"
                                                                    "text-align:center;"
                                                                    "padding:8px;"
                                                                    "color:#ddd;"
                                                                ),
                                                            )
                                            with vuetify.Template(v_if="!(tile && tile.variable_name)"):
                                                with html.Div(classes="catnip-empty-cell"):
                                                    html.Div("+", classes="catnip-empty-plus")
                                                    html.Div("Drop variable here", classes="catnip-empty-hover-label")

                        html.Div(style="height: 8px; flex:0 0 auto;")

                        with vuetify.VCard(variant="outlined", style="flex:0 0 auto;"):
                            with vuetify.VCardText(class_="py-2"):
                                with vuetify.Template(v_if="detailsSelectedVar"):
                                    with html.Div(style="display:flex; align-items:center; gap:12px; width:100%;"):
                                        html.Div("{{ 'Details: ' + detailsSelectedVar }}", class_="text-body-2")
                                        vuetify.VBtn(
                                            "{{ 'SOURCES(' + detailsNumSources + ')' }}",
                                            variant="tonal",
                                            size="small",
                                            click=ctrl.toggle_sources,
                                        )
                                        with html.Div(
                                            class_="text-caption",
                                            style="display:flex; align-items:center; gap:12px; white-space:nowrap;",
                                        ):
                                            html.Span("Min/Max")
                                            with html.Span():
                                                html.Strong("Global ")
                                                html.Span("{{ detailsGlobalMin + ' / ' + detailsGlobalMax }}")
                                            with html.Span():
                                                html.Strong("Median ")
                                                html.Span("{{ detailsMedianMin + ' / ' + detailsMedianMax }}")
                                            with html.Span():
                                                html.Strong("Mean ")
                                                html.Span("{{ detailsMeanMin + ' / ' + detailsMeanMax }}")
                                        vuetify.VSpacer()
                                        html.Div("{{ 'QueryView: ' + queryViewLabel }}", class_="text-caption")
                                with vuetify.Template(v_if="!detailsSelectedVar"):
                                    html.Div("Select a variable", class_="text-caption")

                        with vuetify.VDialog(v_model=("showSourcesModal",), max_width="1200"):
                            with vuetify.VCard():
                                with vuetify.VCardTitle():
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div("{{ sourceDialogTitle || 'Sources' }}")
                                        vuetify.VSpacer()
                                        vuetify.VBtn("Close", variant="text", size="small", click=ctrl.cancel_source_dialog)

                                with vuetify.VCardText():
                                    with vuetify.Template(v_if="detailsSelectedVar"):
                                        with html.Div(
                                            style=(
                                                "display:flex;"
                                                "align-items:center;"
                                                "gap:8px;"
                                                "margin-bottom:8px;"
                                            )
                                        ):
                                            html.Span(
                                                "Filter Sources:",
                                                class_="text-caption",
                                                style="white-space:nowrap;",
                                            )
                                            vuetify.VBtn(
                                                "?",
                                                variant="tonal",
                                                size="small",
                                                min_width=32,
                                                title="Source filter help",
                                                click=ctrl.show_source_filter_help,
                                            )
                                            vuetify.VTextField(
                                                v_model=("sourceFilterDraftText",),
                                                placeholder="e.g. contains(producer, 'F0.03968') and min > 0.32",
                                                density="compact",
                                                hide_details=True,
                                                variant="outlined",
                                                style="max-width:620px; min-width:360px;",
                                            )
                                            vuetify.VBtn(
                                                "Filter",
                                                variant="tonal",
                                                size="small",
                                                click=ctrl.apply_source_dialog_filter,
                                            )
                                            with vuetify.Template(v_if="sourceDialogMode === 'add'"):
                                                vuetify.VBtn(
                                                    "Select All",
                                                    variant="tonal",
                                                    size="small",
                                                    click=ctrl.select_all_sources,
                                                )
                                                vuetify.VBtn(
                                                    "Clear All",
                                                    variant="text",
                                                    size="small",
                                                    click=ctrl.clear_all_sources,
                                                )
                                        with vuetify.Template(v_if="sourceFilterError"):
                                            html.Div("{{ sourceFilterError }}", class_="text-caption mb-2", style="color:#b00020;")
                                        with vuetify.Template(v_if="sourceDialogStatus && sourceDialogStatusIsError"):
                                            html.Div("{{ sourceDialogStatus }}", class_="text-caption mb-2", style="color:#b00020;")
                                        with vuetify.Template(v_if="sourceDialogStatus && !sourceDialogStatusIsError"):
                                            html.Div("{{ sourceDialogStatus }}", class_="text-caption mb-2", style="color:#2e7d32;")
                                        html.Div(
                                            "{{ ((sourceDialogMode === 'add') ? 'Selected sources: ' : 'Selected source: ') + selectedSourceLabel }}",
                                            class_="text-caption mb-2",
                                        )
                                        with html.Div(
                                            style=(
                                                "max-height:60vh;"
                                                "overflow-y:auto;"
                                                "overflow-x:scroll;"
                                                "white-space:nowrap;"
                                                "scrollbar-gutter:stable;"
                                            )
                                        ):
                                            with vuetify.VTable(density="compact"):
                                                with html.Thead():
                                                    with html.Tr():
                                                        with html.Th(
                                                            style="cursor:pointer; user-select:none; white-space:nowrap; width:72px;",
                                                            click=(ctrl.sort_sources, "['show']"),
                                                        ):
                                                            html.Span("Selected")
                                                            with vuetify.Template(v_if="sourceSortField === 'show'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_if="sourceSortField !== 'show'"):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")
                                                        with html.Th(
                                                            style="cursor:pointer; user-select:none; white-space:nowrap;",
                                                            click=(ctrl.sort_sources, "['source_dataset']"),
                                                        ):
                                                            html.Span("source dataset")
                                                            with vuetify.Template(v_if="sourceSortField === 'source_dataset'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_if="sourceSortField !== 'source_dataset'"):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")

                                                        with html.Th(
                                                            style="cursor:pointer; user-select:none; white-space:nowrap;",
                                                            click=(ctrl.sort_sources, "['min']"),
                                                        ):
                                                            html.Span("min")
                                                            with vuetify.Template(v_if="sourceSortField === 'min'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_if="sourceSortField !== 'min'"):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")

                                                        with html.Th(
                                                            style="cursor:pointer; user-select:none; white-space:nowrap;",
                                                            click=(ctrl.sort_sources, "['max']"),
                                                        ):
                                                            html.Span("max")
                                                            with vuetify.Template(v_if="sourceSortField === 'max'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_if="sourceSortField !== 'max'"):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")
                                                with html.Tbody():
                                                    with vuetify.Template(v_for="(r, i) in sourceRows", key="i"):
                                                        with html.Tr(
                                                            style=(
                                                                "((selectedSourceKeys || []).includes(r._key)) ? "
                                                                "'background-color:#f5f5f5; cursor:pointer;' : "
                                                                "'cursor:pointer;'",
                                                            ),
                                                            click=(ctrl.source_dialog_select, "[r._key]"),
                                                        ):
                                                            with html.Td(style="text-align:center; white-space:nowrap;"):
                                                                with vuetify.Template(v_if="sourceDialogMode === 'add'"):
                                                                    html.Input(
                                                                        type="checkbox",
                                                                        checked=("((selectedSourceKeys || []).includes(r._key))",),
                                                                    )
                                                                with vuetify.Template(v_if="sourceDialogMode !== 'add'"):
                                                                    html.Input(
                                                                        type="radio",
                                                                        name="selected-source",
                                                                        checked=("((selectedSourceKeys || []).includes(r._key))",),
                                                                    )
                                                            html.Td(
                                                                "{{ r.sourceName || r.source_label || r.source_dataset || [r.producer, r.casename, r.file].filter(Boolean).join('/') }}",
                                                                style="white-space:nowrap;",
                                                            )
                                                            html.Td("{{ r.min }}", style="white-space:nowrap;")
                                                            html.Td("{{ r.max }}", style="white-space:nowrap;")
                                        with vuetify.Template(v_if="!detailsSelectedVar"):
                                            html.Div("Select a variable first.", class_="text-caption")
                                with vuetify.VCardActions():
                                    vuetify.VSpacer()
                                    vuetify.VBtn("Cancel", variant="text", click=ctrl.cancel_source_dialog)
                                    vuetify.VBtn("Apply", variant="tonal", click=ctrl.apply_source_dialog)

                        with vuetify.VDialog(v_model=("showScalarPlotDialog",), max_width="560"):
                            with vuetify.VCard():
                                vuetify.VCardTitle("Generate Scalar Plot")
                                with vuetify.VCardText():
                                    html.Div("{{ scalarPlotDialogMessage }}", class_="text-body-2")
                                    vuetify.VCheckbox(
                                        v_model=("scalarPlotAlwaysForSession",),
                                        label="Always generate scalar plots for this session",
                                        density="compact",
                                        hide_details=True,
                                        class_="mt-3",
                                    )
                                with vuetify.VCardActions():
                                    vuetify.VSpacer()
                                    vuetify.VBtn(
                                        "Cancel",
                                        variant="text",
                                        click=ctrl.cancel_scalar_plot_generation,
                                    )
                                    vuetify.VBtn(
                                        "Generate",
                                        variant="tonal",
                                        click=ctrl.confirm_scalar_plot_generation,
                                    )

                        with html.Div(
                            id="catnip-plot-settings-panel",
                            v_show=("showPlotSettingsModal",),
                            classes="catnip-floating-options-panel catnip-plot-settings-panel",
                        ):
                            with vuetify.VCard(classes="catnip-floating-options-card", elevation=6):
                                with vuetify.VCardTitle(classes="catnip-floating-options-titlebar"):
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div(
                                            "{{ 'Plot Settings: ' + (plotSettingsTitle || '') }}",
                                            classes="catnip-floating-panel-drag-handle",
                                        )
                                        vuetify.VSpacer()
                                        vuetify.VBtn("Close", variant="text", size="small", click=ctrl.cancel_plot_settings)

                                with vuetify.VCardText(classes="catnip-floating-options-content"):
                                    with vuetify.Template(v_if="plotSettingsStatus"):
                                        html.Div("{{ plotSettingsStatus }}", class_="text-caption mb-2", style="color:#b00020;")

                                    html.Div("Grid", classes="catnip-plot-settings-section-title")
                                    with html.Div(classes="catnip-plot-settings-section"):
                                        with html.Div(classes="catnip-plot-settings-grid-controls"):
                                            with html.Div(classes="catnip-plot-settings-background-control"):
                                                html.Span("Background", class_="text-caption")
                                                with html.Div(classes="catnip-plot-settings-color-menu"):
                                                    html.Button(
                                                        "",
                                                        classes="catnip-plot-settings-current-color",
                                                        raw_attrs=[
                                                            'type="button"',
                                                            ':title="\'Background: \' + (plotSettingsBackgroundColor || \'\')"',
                                                            ':style="{ backgroundColor: plotSettingsBackgroundColor || \'#ffffff\' }"',
                                                        ],
                                                    )
                                                    with vuetify.VMenu(
                                                        activator="parent",
                                                        location="bottom end",
                                                        close_on_content_click=False,
                                                    ):
                                                        with vuetify.VCard(classes="catnip-plot-settings-color-popup", elevation=4):
                                                            with vuetify.VCardText(class_="pa-2"):
                                                                html.Div("Standard Colors", classes="text-caption catnip-plot-settings-popup-title")
                                                                with html.Div(classes="catnip-plot-settings-standard-colors"):
                                                                    with vuetify.Template(
                                                                        v_for="color in plotSettingsStandardColors",
                                                                        key="'background:' + color",
                                                                    ):
                                                                        html.Button(
                                                                            "",
                                                                            classes="catnip-plot-settings-color-swatch",
                                                                            raw_attrs=[
                                                                                'type="button"',
                                                                                ':title="color"',
                                                                                ':style="{ backgroundColor: color, boxShadow: ((plotSettingsBackgroundColor || \'\').toLowerCase() === color.toLowerCase()) ? \'0 0 0 2px #111\' : \'none\' }"',
                                                                            ],
                                                                            click=(ctrl.update_plot_background_color, "[color]"),
                                                                        )
                                                                html.Div("More colors...", classes="text-caption catnip-plot-settings-more-colors")
                                                                vuetify.VColorPicker(
                                                                    hide_header=True,
                                                                    hide_inputs=False,
                                                                    show_swatches=False,
                                                                    width=220,
                                                                    raw_attrs=[
                                                                        ':model-value="plotSettingsBackgroundColor"',
                                                                        ':modes="[\'hex\', \'rgb\', \'hsl\']"',
                                                                    ],
                                                                    update_modelValue=(ctrl.update_plot_background_color, "[$event]"),
                                                                )
                                            with html.Div(
                                                classes="catnip-plot-settings-background-control",
                                                raw_attrs=[':style="{ opacity: plotSettingsShowGrid ? 1 : 0.45 }"'],
                                            ):
                                                vuetify.VCheckbox(
                                                    v_model=("plotSettingsShowGrid",),
                                                    density="compact",
                                                    hide_details=True,
                                                    classes="catnip-plot-settings-toggle",
                                                )
                                                html.Span("Grid lines", class_="text-caption")
                                                with html.Div(classes="catnip-plot-settings-color-menu"):
                                                    html.Button(
                                                        "",
                                                        classes="catnip-plot-settings-current-color",
                                                        raw_attrs=[
                                                            'type="button"',
                                                            ':disabled="!plotSettingsShowGrid"',
                                                            ':title="\'Grid lines: \' + (plotSettingsGridColor || \'\')"',
                                                            ':style="{ backgroundColor: plotSettingsGridColor || \'#e8e8e8\', cursor: plotSettingsShowGrid ? \'pointer\' : \'not-allowed\' }"',
                                                        ],
                                                    )
                                                    with vuetify.VMenu(
                                                        activator="parent",
                                                        location="bottom end",
                                                        close_on_content_click=False,
                                                        raw_attrs=[':disabled="!plotSettingsShowGrid"'],
                                                    ):
                                                        with vuetify.VCard(classes="catnip-plot-settings-color-popup", elevation=4):
                                                            with vuetify.VCardText(class_="pa-2"):
                                                                html.Div("Standard Colors", classes="text-caption catnip-plot-settings-popup-title")
                                                                with html.Div(classes="catnip-plot-settings-standard-colors"):
                                                                    with vuetify.Template(
                                                                        v_for="color in plotSettingsStandardColors",
                                                                        key="'grid:' + color",
                                                                    ):
                                                                        html.Button(
                                                                            "",
                                                                            classes="catnip-plot-settings-color-swatch",
                                                                            raw_attrs=[
                                                                                'type="button"',
                                                                                ':disabled="!plotSettingsShowGrid"',
                                                                                ':title="color"',
                                                                                ':style="{ backgroundColor: color, boxShadow: ((plotSettingsGridColor || \'\').toLowerCase() === color.toLowerCase()) ? \'0 0 0 2px #111\' : \'none\' }"',
                                                                            ],
                                                                            click=(ctrl.update_plot_grid_color, "[color]"),
                                                                        )
                                                                html.Div("More colors...", classes="text-caption catnip-plot-settings-more-colors")
                                                                vuetify.VColorPicker(
                                                                    hide_header=True,
                                                                    hide_inputs=False,
                                                                    show_swatches=False,
                                                                    width=220,
                                                                    raw_attrs=[
                                                                        ':model-value="plotSettingsGridColor"',
                                                                        ':modes="[\'hex\', \'rgb\', \'hsl\']"',
                                                                        ':disabled="!plotSettingsShowGrid"',
                                                                    ],
                                                                    update_modelValue=(ctrl.update_plot_grid_color, "[$event]"),
                                                                )
                                            with html.Div(
                                                classes="catnip-plot-settings-background-control",
                                                raw_attrs=[':style="{ opacity: plotSettingsShowCursor ? 1 : 0.45 }"'],
                                            ):
                                                vuetify.VCheckbox(
                                                    v_model=("plotSettingsShowCursor",),
                                                    density="compact",
                                                    hide_details=True,
                                                    classes="catnip-plot-settings-toggle",
                                                )
                                                html.Span("Cursor", class_="text-caption")
                                                with html.Div(classes="catnip-plot-settings-color-menu"):
                                                    html.Button(
                                                        "",
                                                        classes="catnip-plot-settings-current-color",
                                                        raw_attrs=[
                                                            'type="button"',
                                                            ':disabled="!plotSettingsShowCursor"',
                                                            ':title="\'Cursor: \' + (plotSettingsCursorColor || \'\')"',
                                                            ':style="{ backgroundColor: plotSettingsCursorColor || \'#111111\', cursor: plotSettingsShowCursor ? \'pointer\' : \'not-allowed\' }"',
                                                        ],
                                                    )
                                                    with vuetify.VMenu(
                                                        activator="parent",
                                                        location="bottom end",
                                                        close_on_content_click=False,
                                                        raw_attrs=[':disabled="!plotSettingsShowCursor"'],
                                                    ):
                                                        with vuetify.VCard(classes="catnip-plot-settings-color-popup", elevation=4):
                                                            with vuetify.VCardText(class_="pa-2"):
                                                                html.Div("Standard Colors", classes="text-caption catnip-plot-settings-popup-title")
                                                                with html.Div(classes="catnip-plot-settings-standard-colors"):
                                                                    with vuetify.Template(
                                                                        v_for="color in plotSettingsStandardColors",
                                                                        key="'cursor:' + color",
                                                                    ):
                                                                        html.Button(
                                                                            "",
                                                                            classes="catnip-plot-settings-color-swatch",
                                                                            raw_attrs=[
                                                                                'type="button"',
                                                                                ':disabled="!plotSettingsShowCursor"',
                                                                                ':title="color"',
                                                                                ':style="{ backgroundColor: color, boxShadow: ((plotSettingsCursorColor || \'\').toLowerCase() === color.toLowerCase()) ? \'0 0 0 2px #111\' : \'none\' }"',
                                                                            ],
                                                                            click=(ctrl.update_plot_cursor_color, "[color]"),
                                                                        )
                                                                html.Div("More colors...", classes="text-caption catnip-plot-settings-more-colors")
                                                                vuetify.VColorPicker(
                                                                    hide_header=True,
                                                                    hide_inputs=False,
                                                                    show_swatches=False,
                                                                    width=220,
                                                                    raw_attrs=[
                                                                        ':model-value="plotSettingsCursorColor"',
                                                                        ':modes="[\'hex\', \'rgb\', \'hsl\']"',
                                                                        ':disabled="!plotSettingsShowCursor"',
                                                                    ],
                                                                    update_modelValue=(ctrl.update_plot_cursor_color, "[$event]"),
                                                                )

                                    html.Div("Axes", classes="catnip-plot-settings-section-title mt-3")
                                    with html.Div(classes="catnip-plot-settings-section"):
                                        with html.Div(classes="catnip-plot-settings-axis-list"):
                                            with html.Div(classes="catnip-plot-settings-axis-row"):
                                                html.Span("X:", classes="catnip-plot-settings-axis-label")
                                                vuetify.VCheckbox(
                                                    v_model=("plotSettingsXAuto",),
                                                    label="Auto range",
                                                    density="compact",
                                                    hide_details=True,
                                                )
                                                vuetify.VTextField(
                                                    v_model=("plotSettingsXMin",),
                                                    label="Min",
                                                    density="compact",
                                                    hide_details=True,
                                                    raw_attrs=[':disabled="plotSettingsXAuto"'],
                                                )
                                                vuetify.VTextField(
                                                    v_model=("plotSettingsXMax",),
                                                    label="Max",
                                                    density="compact",
                                                    hide_details=True,
                                                    raw_attrs=[':disabled="plotSettingsXAuto"'],
                                                )
                                                html.Span("Scale", class_="text-caption")
                                                with html.Select(
                                                    v_model=("plotSettingsXScale",),
                                                    classes="catnip-scalar-plot-policy",
                                                ):
                                                    html.Option("Linear", value="linear")
                                                    html.Option("Log", value="log")

                                            with html.Div(classes="catnip-plot-settings-axis-row"):
                                                html.Span("Y:", classes="catnip-plot-settings-axis-label")
                                                vuetify.VCheckbox(
                                                    v_model=("plotSettingsYAuto",),
                                                    label="Auto range",
                                                    density="compact",
                                                    hide_details=True,
                                                )
                                                vuetify.VTextField(
                                                    v_model=("plotSettingsYMin",),
                                                    label="Min",
                                                    density="compact",
                                                    hide_details=True,
                                                    raw_attrs=[':disabled="plotSettingsYAuto"'],
                                                )
                                                vuetify.VTextField(
                                                    v_model=("plotSettingsYMax",),
                                                    label="Max",
                                                    density="compact",
                                                    hide_details=True,
                                                    raw_attrs=[':disabled="plotSettingsYAuto"'],
                                                )
                                                html.Span("Scale", class_="text-caption")
                                                with html.Select(
                                                    v_model=("plotSettingsYScale",),
                                                    classes="catnip-scalar-plot-policy",
                                                ):
                                                    html.Option("Linear", value="linear")
                                                    html.Option("Log", value="log")

                                    html.Div("Curves", classes="catnip-plot-settings-section-title mt-3")
                                    with html.Div(classes="catnip-plot-settings-section"):
                                        with html.Div(classes="catnip-plot-settings-curves-layout"):
                                            with html.Div(classes="catnip-plot-settings-curve-controls"):
                                                vuetify.VTextField(
                                                    v_model=("plotSettingsLineWidth",),
                                                    label="Line width",
                                                    density="compact",
                                                    hide_details=True,
                                                    raw_attrs=['type="number"', 'min="0.5"', 'max="8"', 'step="0.5"'],
                                                    style="max-width:160px;",
                                                )
                                            with html.Div(classes="catnip-plot-settings-color-list"):
                                                with html.Div(v_if="!(plotSettingsSeriesRows || []).length", class_="text-caption"):
                                                    html.Span("No series")
                                                with vuetify.Template(v_for="row in plotSettingsSeriesRows", key="row.key"):
                                                    with html.Div(classes="catnip-plot-settings-series-row"):
                                                        with html.Div(classes="catnip-plot-settings-color-menu"):
                                                            html.Button(
                                                                "",
                                                                classes="catnip-plot-settings-current-color",
                                                                raw_attrs=[
                                                                    'type="button"',
                                                                    ':title="\'Color: \' + (row.color || \'\')"',
                                                                    ':style="{ backgroundColor: row.color || \'#1565c0\' }"',
                                                                ],
                                                            )
                                                            with vuetify.VMenu(
                                                                activator="parent",
                                                                location="bottom end",
                                                                close_on_content_click=False,
                                                            ):
                                                                with vuetify.VCard(classes="catnip-plot-settings-color-popup", elevation=4):
                                                                    with vuetify.VCardText(class_="pa-2"):
                                                                        html.Div("Standard Colors", classes="text-caption catnip-plot-settings-popup-title")
                                                                        with html.Div(classes="catnip-plot-settings-standard-colors"):
                                                                            with vuetify.Template(
                                                                                v_for="color in plotSettingsStandardColors",
                                                                                key="row.key + ':' + color",
                                                                            ):
                                                                                html.Button(
                                                                                    "",
                                                                                    classes="catnip-plot-settings-color-swatch",
                                                                                    raw_attrs=[
                                                                                        'type="button"',
                                                                                        ':title="color"',
                                                                                        ':style="{ backgroundColor: color, boxShadow: ((row.color || \'\').toLowerCase() === color.toLowerCase()) ? \'0 0 0 2px #111\' : \'none\' }"',
                                                                                    ],
                                                                                    click=(ctrl.update_plot_series_color, "[row.key, color]"),
                                                                                )
                                                                        html.Div("More colors...", classes="text-caption catnip-plot-settings-more-colors")
                                                                        vuetify.VColorPicker(
                                                                            hide_header=True,
                                                                            hide_inputs=False,
                                                                            show_swatches=False,
                                                                            width=220,
                                                                            raw_attrs=[
                                                                                ':model-value="row.color"',
                                                                                ':modes="[\'hex\', \'rgb\', \'hsl\']"',
                                                                            ],
                                                                            update_modelValue=(ctrl.update_plot_series_color, "[row.key, $event]"),
                                                                        )
                                                        html.Div(
                                                            "{{ row.label }}",
                                                            class_="text-caption catnip-plot-settings-series-label",
                                                        )
                                                        with html.Select(
                                                            classes="catnip-plot-settings-line-style",
                                                            raw_attrs=[':value="row.line_style || \'solid\'"'],
                                                            change=(ctrl.update_plot_series_line_style, "[row.key, $event.target.value]"),
                                                        ):
                                                            html.Option("Solid", value="solid")
                                                            html.Option("Dash", value="dash")
                                                            html.Option("Dot", value="dot")
                                                            html.Option("Dash-dot", value="dash-dot")

                                with vuetify.VCardActions():
                                    with vuetify.Template(v_if="plotSettingsCanPluginOptions"):
                                        vuetify.VBtn("Plugin options...", variant="text", click=ctrl.open_plot_settings_plugin_options)
                                    vuetify.VSpacer()
                                    vuetify.VBtn("Reset", variant="text", click=ctrl.reset_plot_settings)
                                    vuetify.VBtn("Cancel", variant="text", click=ctrl.cancel_plot_settings)
                                    vuetify.VBtn("Apply", variant="tonal", click=ctrl.apply_plot_settings)

                        with html.Div(
                            id="catnip-plugin-options-panel",
                            v_show=("showPluginOptionsModal",),
                            classes="catnip-floating-options-panel",
                        ):
                            with vuetify.VCard(classes="catnip-floating-options-card", elevation=6):
                                with vuetify.VCardTitle(classes="catnip-floating-options-titlebar"):
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div(
                                            "{{ 'Plugin Options: ' + (pluginOptionsTitle || '') }}",
                                            classes="catnip-floating-panel-drag-handle",
                                        )
                                        vuetify.VSpacer()
                                        vuetify.VBtn("Close", variant="text", size="small", click=ctrl.cancel_plugin_options)

                                with vuetify.VCardText(classes="catnip-floating-options-content"):
                                    with vuetify.Template(v_if="pluginOptionsStatus"):
                                        html.Div("{{ pluginOptionsStatus }}", class_="text-caption mb-2", style="color:#b00020;")
                                    with vuetify.Template(v_if="!(pluginOptionsRows || []).length"):
                                        html.Div("No plugin-specific options.", class_="text-caption")
                                    with html.Div(classes="catnip-plugin-options-list"):
                                        with vuetify.Template(v_for="row in pluginOptionsRows", key="row.key"):
                                            with html.Div(classes="catnip-plugin-option-row"):
                                                html.Span("{{ row.label }}", classes="catnip-plugin-option-label")
                                                with html.Div(classes="catnip-plugin-option-control"):
                                                    with vuetify.Template(v_if="row.type === 'bool'"):
                                                        html.Input(
                                                            classes="catnip-plugin-option-checkbox",
                                                            raw_attrs=[
                                                                'type="checkbox"',
                                                                ':checked="!!row.value"',
                                                            ],
                                                            change=(ctrl.update_plugin_option_value, "[row.key, $event.target.checked]"),
                                                        )
                                                    with vuetify.Template(v_if="row.type === 'select'"):
                                                        with html.Select(
                                                            classes="catnip-scalar-plot-policy catnip-plugin-option-select",
                                                            raw_attrs=[':value="row.value"'],
                                                            change=(ctrl.update_plugin_option_value, "[row.key, $event.target.value]"),
                                                        ):
                                                            with vuetify.Template(v_for="choice in row.choices", key="choice"):
                                                                html.Option("{{ choice }}", raw_attrs=[':value="choice"'])
                                                    with vuetify.Template(v_if="row.type !== 'bool' && row.type !== 'select'"):
                                                        html.Input(
                                                            classes="catnip-plugin-option-input",
                                                            raw_attrs=[
                                                                ':type="row.type === \'number\' ? \'number\' : \'text\'"',
                                                                ':value="row.value"',
                                                            ],
                                                            change=(ctrl.update_plugin_option_value, "[row.key, $event.target.value]"),
                                                        )

                                with vuetify.VCardActions():
                                    vuetify.VSpacer()
                                    vuetify.VBtn("Reset", variant="text", click=ctrl.reset_plugin_options)
                                    vuetify.VBtn("Cancel", variant="text", click=ctrl.cancel_plugin_options)
                                    vuetify.VBtn("Apply", variant="tonal", click=ctrl.apply_plugin_options)

                        with html.Div(
                            id="catnip-scalar-field-settings-panel",
                            v_show=("showScalarFieldSettingsModal",),
                            classes="catnip-floating-options-panel",
                        ):
                            with vuetify.VCard(classes="catnip-floating-options-card", elevation=6):
                                with vuetify.VCardTitle(classes="catnip-floating-options-titlebar"):
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div(
                                            "{{ 'Plot Options: ' + (scalarFieldSettingsTitle || '') }}",
                                            classes="catnip-floating-panel-drag-handle",
                                        )
                                        vuetify.VSpacer()
                                        vuetify.VBtn(
                                            "Close",
                                            variant="text",
                                            size="small",
                                            click=ctrl.cancel_scalar_field_settings,
                                        )

                                with vuetify.VCardText(classes="catnip-floating-options-content"):
                                    with vuetify.Template(v_if="scalarFieldSettingsStatus"):
                                        html.Div(
                                            "{{ scalarFieldSettingsStatus }}",
                                            class_="text-caption mb-2",
                                            raw_attrs=[
                                                ':style="{ color: scalarFieldSettingsStatusIsError ? \'#b00020\' : \'#1b5e20\' }"'
                                            ],
                                        )

                                    html.Div("Color", classes="catnip-plot-settings-section-title")
                                    with html.Div(classes="catnip-plot-settings-section"):
                                        with html.Div(classes="catnip-plot-settings-row"):
                                            html.Span("Colormap", class_="text-caption")
                                            with html.Select(
                                                v_model=("scalarFieldSettingsColormap",),
                                                classes="catnip-scalar-plot-policy catnip-scalar-field-colormap",
                                            ):
                                                for label, value in SCALAR_FIELD_COLORMAP_OPTIONS:
                                                    html.Option(label, value=value)

                                    html.Div("Range", classes="catnip-plot-settings-section-title mt-3")
                                    with html.Div(classes="catnip-plot-settings-section"):
                                        with html.Div(classes="catnip-plot-settings-axis-row catnip-scalar-field-range-row"):
                                            with html.Div(classes="catnip-scalar-field-auto-control"):
                                                html.Input(
                                                    v_model=("scalarFieldSettingsRangeAuto",),
                                                    classes="catnip-scalar-field-auto-checkbox",
                                                    raw_attrs=['type="checkbox"'],
                                                )
                                                html.Span("Auto")
                                            html.Span(
                                                "Values:",
                                                classes="catnip-plot-settings-axis-label",
                                                raw_attrs=[
                                                    ':class="{ \'is-disabled\': scalarFieldSettingsRangeAuto }"'
                                                ],
                                            )
                                            vuetify.VTextField(
                                                v_model=("scalarFieldSettingsMin",),
                                                label="Min",
                                                density="compact",
                                                hide_details=True,
                                                raw_attrs=[':disabled="scalarFieldSettingsRangeAuto"'],
                                            )
                                            vuetify.VTextField(
                                                v_model=("scalarFieldSettingsMax",),
                                                label="Max",
                                                density="compact",
                                                hide_details=True,
                                                raw_attrs=[':disabled="scalarFieldSettingsRangeAuto"'],
                                            )

                                    html.Div("Display", classes="catnip-plot-settings-section-title mt-3")
                                    with html.Div(classes="catnip-plot-settings-section"):
                                        with html.Div(classes="catnip-scalar-field-display-options"):
                                            with html.Div(classes="catnip-scalar-field-auto-control"):
                                                html.Input(
                                                    v_model=("scalarFieldSettingsShowColorbar",),
                                                    classes="catnip-scalar-field-auto-checkbox",
                                                    raw_attrs=['type="checkbox"'],
                                                )
                                                html.Span("Show color map")
                                            with html.Div(classes="catnip-scalar-field-auto-control"):
                                                html.Input(
                                                    v_model=("scalarFieldSettingsShowAxes",),
                                                    classes="catnip-scalar-field-auto-checkbox",
                                                    raw_attrs=['type="checkbox"'],
                                                )
                                                html.Span("Show axes")

                                with vuetify.VCardActions():
                                    vuetify.VSpacer()
                                    vuetify.VBtn("Reset", variant="text", click=ctrl.reset_scalar_field_settings)
                                    vuetify.VBtn("Close", variant="text", click=ctrl.cancel_scalar_field_settings)
                                    vuetify.VBtn("Apply", variant="tonal", click=ctrl.apply_scalar_field_settings)

            with html.Div(
                id="catnip-context-menu",
                v_show=("contextMenuVisible",),
                raw_attrs=[
                    ':style="{ position: \'fixed\', zIndex: 9999, left: (contextMenuX || 0) + \'px\', top: (contextMenuY || 0) + \'px\' }"'
                ],
            ):
                html.Div("{{ contextMenuItemLabel || contextMenuItem || 'Menu' }}", classes="menu-label")

                with html.Div(v_if="contextMenuKind === 'item'"):
                    html.Div("Add To Grid", classes="menu-item", click=ctrl.context_menu_item_add)
                    html.Div("Select Variable", classes="menu-item", click=ctrl.context_menu_item_select)

                with html.Div(v_if="contextMenuKind === 'cell'"):
                    html.Div("Select Cell", classes="menu-item", click=ctrl.context_menu_cell_select)
                    with vuetify.Template(v_if="contextMenuCellCanResetView"):
                        html.Div("Reset View", classes="menu-item", click=ctrl.context_menu_cell_reset_view)
                    html.Div("Clear Cell", classes="menu-item danger", click=ctrl.context_menu_cell_clear)
                    with vuetify.Template(v_if="gridLayoutMode === 'spanning'"):
                        with html.Div(classes="menu-submenu"):
                            with html.Div(classes="menu-item menu-submenu-trigger"):
                                html.Span("Span")
                                html.Span("›", classes="menu-submenu-arrow")
                            with html.Div(classes="menu-submenu-panel"):
                                html.Div("Span right", classes="menu-item", click=ctrl.context_menu_cell_span_right)
                                html.Div("Span down", classes="menu-item", click=ctrl.context_menu_cell_span_down)
                                html.Div("Shrink width", classes="menu-item", click=ctrl.context_menu_cell_shrink_width)
                                html.Div("Shrink height", classes="menu-item", click=ctrl.context_menu_cell_shrink_height)
                                html.Div("Reset span", classes="menu-item", click=ctrl.context_menu_cell_reset_span)
                    with vuetify.Template(v_if="contextMenuCellHasVariable && !contextMenuCellCanPlotSettings"):
                        html.Div("Sources...", classes="menu-item", click=ctrl.context_menu_cell_sources)
                    with vuetify.Template(v_if="contextMenuCellCanAddSource"):
                        html.Div("Add Source", classes="menu-item", click=ctrl.context_menu_cell_add_source)
                    with vuetify.Template(v_if="contextMenuCellCanPlotSettings"):
                        html.Div("Plot settings...", classes="menu-item", click=ctrl.context_menu_cell_plot_settings)
                    with vuetify.Template(v_if="contextMenuCellCanScalarFieldSettings"):
                        html.Div("Plot options...", classes="menu-item", click=ctrl.context_menu_cell_scalar_field_settings)
                    with vuetify.Template(v_if="(contextMenuCellSourcePlugins || []).length"):
                        html.Div("Run Plugin", classes="menu-section")
                        with vuetify.Template(v_for="plugin in contextMenuCellSourcePlugins", key="plugin.plugin_id"):
                            html.Div(
                                "{{ plugin.label }}",
                                classes="menu-item",
                                click=(ctrl.context_menu_cell_run_source_plugin, "[plugin.plugin_id]"),
                            )
                    with vuetify.Template(v_if="(contextMenuCellVisualizationOptions || []).length"):
                        html.Div("Visualization Type", classes="menu-section")
                        with vuetify.Template(v_for="vis in contextMenuCellVisualizationOptions", key="vis"):
                            html.Div(
                                "{{ ((vis === contextMenuCellSelectedVisualization) ? '✓ ' : '') + vis }}",
                                classes="menu-item",
                                click=(ctrl.context_menu_cell_pick_visualization, "[vis]"),
                            )

    return layout
