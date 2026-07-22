(function initSeuratClient() {
  try {
    if (typeof window.trame === "undefined") {
      setTimeout(initSeuratClient, 200);
      return;
    }
    let gridRuntimeRoot = null;

    function gridRuntimeQuery(selector) {
      const root = gridRuntimeRoot || document;
      return root.querySelector ? root.querySelector(selector) : null;
    }

    function gridRuntimeQueryAll(selector) {
      const root = gridRuntimeRoot || document;
      return root.querySelectorAll ? root.querySelectorAll(selector) : [];
    }

    function gridRuntimeElementById(id) {
      return gridRuntimeQuery("#" + id);
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
      return Array.from(gridRuntimeQueryAll('img[data-grid-image-sequence="1"]'));
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

    function imageSequenceHasPhysicalTime(el) {
      const mode = String(el && el.getAttribute && el.getAttribute("data-time-mode") || "").trim().toLowerCase();
      return mode === "physical_time" && parseImageSequenceTimeValues(el).length > 0;
    }

    function imageSequencesHavePhysicalTime(sequences) {
      const values = sequences || [];
      return values.length > 0 && values.every(imageSequenceHasPhysicalTime);
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

      const plots = Array.from(cell.querySelectorAll ? cell.querySelectorAll(".seurat-plot1d") : []);
      const sequences = Array.from(cell.querySelectorAll ? cell.querySelectorAll('img[data-grid-image-sequence="1"]') : []);
      const values = [];
      const plotValues = collectPlotTimeValues(plots);
      values.push.apply(values, plotValues);

      let sequenceValueCount = 0;
      for (const el of sequences) {
        if (!imageSequenceHasPhysicalTime(el)) continue;
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
      const cell = gridRuntimeQuery('.seurat-dropcell[data-timeline-driver="1"]');
      return cell && isVisibleGridCell(cell) ? cell : null;
    }

    function autoTimelineDriver() {
      const cells = Array.from(gridRuntimeQueryAll(".seurat-dropcell"));
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
      sequences = sequences || getGridImageSequencesSafe();
      plots = plots || (typeof getGridPlots === "function" ? getGridPlots() : []);
      if (sequences.length && !imageSequencesHavePhysicalTime(sequences)) return [];

      const selected = selectedTimelineDriverCell();
      if (selected) {
        const selectedTimeline = timelineForGridCell(selected);
        if (selectedTimeline.values.length) return selectedTimeline.values;
      }

      const auto = autoTimelineDriver();
      if (auto.values.length) return auto.values;

      const values = [];
      for (const el of (sequences || [])) {
        if (!imageSequenceHasPhysicalTime(el)) continue;
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

      const times = imageSequenceHasPhysicalTime(el) ? parseImageSequenceTimeValues(el) : [];
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
        const times = imageSequenceHasPhysicalTime(el) ? parseImageSequenceTimeValues(el) : [];
        const index = Math.max(0, Math.min(Math.round(frame), Math.max(0, times.length - 1)));
        if (index < times.length) return times[index];
      }
      return getReferenceImageSequenceFrame(sequences);
    }

    function getVcrSliderFrameValue() {
      const slider = gridRuntimeElementById("seurat-vcr-step-slider");
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

      const slider = gridRuntimeElementById("seurat-vcr-step-slider");
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
      const label = gridRuntimeElementById("seurat-vcr-time-value");
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
          label.textContent = "Step = " + imageSequenceFrameLabel(ordinal, sequences);
        } else if (videos && videos.length) {
          const ordinal = frameOrdinalFromTime(safeSeconds, videos);
          label.textContent = "Time = " + videoFrameLabel(ordinal, videos);
        } else {
          label.textContent = (plots.length ? "Step = " : "Time = ") + formatTimelineValue(safeSeconds);
        }
      }

      const slider = gridRuntimeElementById("seurat-vcr-step-slider");
      if (typeof updatePlotCursors === "function") {
        updatePlotCursors(safeSeconds, videos);
      }
      gridVcrState.syncTime = safeSeconds;
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
    const gridVcrState = {
      playing: false,
      syncTime: 0,
      timelinePosition: 0,
      syncTimer: null,
      lastTickMs: 0,
    };
    let gridMediaSyncTimer = null;
    let gridMediaObserver = null;

    function getGridVideos() {
      return Array.from(gridRuntimeQueryAll('video[data-grid-video="1"]'));
    }

    function getGridImageSequences() {
      return Array.from(gridRuntimeQueryAll('img[data-grid-image-sequence="1"]'));
    }

    function isGridVideo(target) {
      return !!(target && target.matches && target.matches('video[data-grid-video="1"]'));
    }

    function getGridPlots() {
      return Array.from(gridRuntimeQueryAll(".seurat-plot1d"));
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
      if (el.__seuratPlotRaw === raw && el.__seuratPlotData) {
        return el.__seuratPlotData;
      }
      if (el.__seuratPlotRaw !== undefined && el.__seuratPlotRaw !== raw) {
        el.__seuratPlotViewState = null;
        el.__seuratPlotRenderKey = "";
      }
      try {
        el.__seuratPlotData = JSON.parse(raw);
        el.__seuratPlotRaw = raw;
      } catch (_err) {
        el.__seuratPlotData = {};
        el.__seuratPlotRaw = raw;
      }
      return el.__seuratPlotData || {};
    }

    function parsePlotSettings(el) {
      if (!el) return {};
      const raw = el.getAttribute("data-plot-settings") || "{}";
      if (el.__seuratPlotSettingsRaw === raw && el.__seuratPlotSettings) {
        return el.__seuratPlotSettings;
      }
      try {
        el.__seuratPlotSettings = JSON.parse(raw);
        el.__seuratPlotSettingsRaw = raw;
      } catch (_err) {
        el.__seuratPlotSettings = {};
        el.__seuratPlotSettingsRaw = raw;
      }
      return el.__seuratPlotSettings || {};
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
      const state = el && el.__seuratPlotViewState;
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
      const state = el && el.__seuratPlotViewState;
      if (!state) return null;
      if (state.xScale !== xAxis.scale || state.yScale !== yAxis.scale) {
        el.__seuratPlotViewState = null;
        return null;
      }
      const viewXAxis = plotAxisFromRange(xAxis, state.xMin, state.xMax);
      const viewYAxis = plotAxisFromRange(yAxis, state.yMin, state.yMax);
      if (!viewXAxis || !viewYAxis) {
        el.__seuratPlotViewState = null;
        return null;
      }
      return { xAxis: viewXAxis, yAxis: viewYAxis };
    }

    function setPlotViewStateFromAxes(el, xAxis, yAxis) {
      if (!el || !xAxis || !yAxis) return;
      el.__seuratPlotViewState = {
        xScale: xAxis.scale,
        yScale: yAxis.scale,
        xMin: xAxis.min,
        xMax: xAxis.max,
        yMin: yAxis.min,
        yMax: yAxis.max,
      };
      el.__seuratPlotRenderKey = "";
    }

    function rerenderPlotView(el) {
      if (!el) return;
      renderPlot1d(el);
      if (typeof updatePlotCursors === "function") {
        updatePlotCursors(gridVcrState.syncTime || 0, getGridVideos());
      }
    }

    function resetPlotView(el) {
      if (!el) return;
      el.__seuratPlotViewState = null;
      el.__seuratPlotRenderKey = "";
      renderPlot1d(el);
      if (typeof updatePlotCursors === "function") {
        updatePlotCursors(gridVcrState.syncTime || 0, getGridVideos());
      }
    }

    function resetPlotViewForCellIndex(cellIndex) {
      const idx = Number(cellIndex);
      if (!Number.isInteger(idx) || idx < 0) return;
      const cell = gridRuntimeQuery('.seurat-dropcell[data-cell-index="' + String(idx) + '"]');
      if (!cell) return;
      const plots = cell.querySelectorAll ? cell.querySelectorAll(".seurat-plot1d") : [];
      for (const el of plots) {
        resetPlotView(el);
      }
    }
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
      const meta = el.__seuratPlotMeta;
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
      const renderKey = String(el.__seuratPlotRaw || "") + "|" + String(el.__seuratPlotSettingsRaw || "") + "|" + width + "x" + height + "|" + plotViewRenderKey(el);
      if (el.__seuratPlotRenderKey === renderKey && el.querySelector("svg")) {
        return;
      }

      el.__seuratPlotRenderKey = renderKey;
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
        cursor.setAttribute("class", "seurat-plot1d-cursor-line");
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
      hoverTip.className = "seurat-plot-hover-tip";
      hoverTip.style.display = "none";
      el.appendChild(hoverTip);

      el.__seuratPlotMeta = {
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
      // Step and physical timelines already use plot x coordinates. Only
      // elapsed video time needs to be normalized onto each plot's domain.
      const progress = bounds.usesVideos
        ? ((t - bounds.start) / denom)
        : null;
      for (const el of plots) {
        const meta = el.__seuratPlotMeta;
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
      const meta = el && el.__seuratPlotMeta;
      if (!meta) return;
      if (meta.hoverGroup) meta.hoverGroup.setAttribute("display", "none");
      if (meta.hoverTip) meta.hoverTip.style.display = "none";
    }

    function hideAllPlotHovers() {
      for (const el of getGridPlots()) {
        hidePlotHover(el);
      }
    }

    let plotViewDrag = null;
    let suppressPlotViewClick = false;
    let plotCtrlDown = false;
    let plotRenderTimer = null;
    let plotResizeObserver = null;
    let plotMutationObserver = null;
    let observedPlots = new Set();
    const PLOT_WHEEL_OPTIONS = { capture: true, passive: false };

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
      const meta = el.__seuratPlotMeta;
      const ctrlActive = !!(event.ctrlKey || plotCtrlDown) && !event.shiftKey;
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

    function plotElementFromEvent(event) {
      const target = event && event.target;
      const plot = target && target.closest ? target.closest(".seurat-plot1d") : null;
      return plot && gridRuntimeRoot && gridRuntimeRoot.contains(plot) ? plot : null;
    }

    function releasePlotPointerCapture(drag) {
      if (!drag || !drag.el || drag.pointerId === undefined) return;
      try {
        if (!drag.el.hasPointerCapture || drag.el.hasPointerCapture(drag.pointerId)) {
          drag.el.releasePointerCapture(drag.pointerId);
        }
      } catch (_) {
        // The pointer may already have been released by the browser.
      }
    }

    function beginPlotViewDrag(event, el, mode) {
      renderPlot1d(el);
      const meta = el.__seuratPlotMeta;
      if (!meta || !meta.xAxis || !meta.yAxis) return;
      finishPlotViewDrag();
      const point = plotLocalPoint(el, event);
      plotViewDrag = {
        el,
        mode,
        startX: Number(event.clientX) || 0,
        startY: Number(event.clientY) || 0,
        pointerId: event.pointerId,
        moved: false,
        xAxis: meta.xAxis,
        yAxis: meta.yAxis,
        plotW: Math.max(1, meta.plotW),
        plotH: Math.max(1, meta.plotH),
        centerX: plotAxisTForLocalPoint(meta.xAxis, meta, point, "x"),
        centerY: plotAxisTForLocalPoint(meta.yAxis, meta, point, "y"),
      };
      el.classList.add(mode === "zoom" ? "is-zooming" : "is-panning");
      document.body.classList.add(
        mode === "zoom" ? "seurat-plot-zooming" : "seurat-plot-panning"
      );
      hidePlotHover(el);
      try {
        el.setPointerCapture(event.pointerId);
      } catch (_) {
        // Pointer capture is best-effort for older browser implementations.
      }
      event.preventDefault();
      event.stopPropagation();
    }

    function updatePlotViewDrag(event) {
      if (!plotViewDrag) return;
      if (
        plotViewDrag.pointerId !== undefined &&
        event.pointerId !== plotViewDrag.pointerId
      ) {
        return;
      }
      const drag = plotViewDrag;
      const dx = (Number(event.clientX) || 0) - drag.startX;
      const dy = (Number(event.clientY) || 0) - drag.startY;
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
      event.preventDefault();
      event.stopPropagation();
    }

    function finishPlotViewDrag(event) {
      if (!plotViewDrag) return;
      const drag = plotViewDrag;
      plotViewDrag = null;
      drag.el.classList.remove("is-panning", "is-zooming");
      document.body.classList.remove("seurat-plot-panning", "seurat-plot-zooming");
      suppressPlotViewClick = !!drag.moved;
      releasePlotPointerCapture(drag);
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }
    }

    function onPlotKeyDown(event) {
      if (event && event.key === "Control") {
        plotCtrlDown = true;
      }
    }

    function onPlotKeyUp(event) {
      if (event && event.key === "Control") {
        plotCtrlDown = false;
        hideAllPlotHovers();
      }
    }

    function onPlotWindowBlur() {
      plotCtrlDown = false;
      hideAllPlotHovers();
      finishPlotViewDrag();
    }

    function onPlotPointerMove(event) {
      if (plotViewDrag) {
        updatePlotViewDrag(event);
        return;
      }
      const el = plotElementFromEvent(event);
      if (!el) return;
      const ctrlActive = !!(event.ctrlKey || plotCtrlDown) && !event.shiftKey;
      if (!ctrlActive) {
        hidePlotHover(el);
        return;
      }
      updatePlotHover(el, event);
    }

    function onPlotPointerDown(event) {
      const el = plotElementFromEvent(event);
      if (!el) return;
      const ctrlActive = !!(event.ctrlKey || plotCtrlDown);
      const isShiftPan = event.button === 0 && event.shiftKey && !ctrlActive;
      const isMiddleZoom = event.button === 1;
      if (isShiftPan || isMiddleZoom) {
        beginPlotViewDrag(event, el, isMiddleZoom ? "zoom" : "pan");
        return;
      }
      if (event.ctrlKey && event.button === 0) {
        event.preventDefault();
        event.stopPropagation();
      }
    }

    function onPlotPointerEnd(event) {
      if (
        plotViewDrag &&
        (plotViewDrag.pointerId === undefined ||
          event.pointerId === plotViewDrag.pointerId)
      ) {
        finishPlotViewDrag(event);
      }
    }

    function onPlotLostPointerCapture(event) {
      if (plotViewDrag && event.target === plotViewDrag.el) {
        finishPlotViewDrag();
      }
    }

    function onPlotWheel(event) {
      const el = plotElementFromEvent(event);
      if (!el) return;
      const rangeFactor = Math.exp((Number(event.deltaY) || 0) * 0.0015);
      zoomPlotViewAt(el, event, rangeFactor);
      hidePlotHover(el);
      event.preventDefault();
      event.stopPropagation();
    }

    function onPlotDoubleClick(event) {
      const el = plotElementFromEvent(event);
      if (!el) return;
      resetPlotView(el);
      event.preventDefault();
      event.stopPropagation();
    }

    function onPlotAuxClick(event) {
      const el = plotElementFromEvent(event);
      if (el && event.button === 1) {
        event.preventDefault();
        event.stopPropagation();
      }
    }

    function onPlotClick(event) {
      if (!suppressPlotViewClick) return;
      suppressPlotViewClick = false;
      const el = plotElementFromEvent(event);
      if (!el) return;
      event.preventDefault();
      event.stopPropagation();
    }

    function onPlotContextMenu(event) {
      const el = plotElementFromEvent(event);
      if (el && event.ctrlKey) {
        event.preventDefault();
        event.stopPropagation();
      }
    }

    function onPlotPointerOut(event) {
      const el = plotElementFromEvent(event);
      if (el && (!event.relatedTarget || !el.contains(event.relatedTarget))) {
        hidePlotHover(el);
      }
    }

    function scheduleRenderAllPlot1d() {
      if (!gridRuntimeRoot) return;
      if (plotRenderTimer) clearTimeout(plotRenderTimer);
      plotRenderTimer = setTimeout(function() {
        plotRenderTimer = null;
        if (!gridRuntimeRoot) return;
        renderAllPlot1d();
        updatePlotCursors(gridVcrState.syncTime || 0, getGridVideos());
      }, 30);
    }

    function observePlot1dSizes() {
      if (!plotResizeObserver) return;
      const currentPlots = new Set(getGridPlots());
      for (const el of observedPlots) {
        if (!currentPlots.has(el)) {
          plotResizeObserver.unobserve(el);
          observedPlots.delete(el);
        }
      }
      for (const el of currentPlots) {
        if (!observedPlots.has(el)) {
          plotResizeObserver.observe(el);
          observedPlots.add(el);
        }
      }
    }

    function mountPlotRuntime(root) {
      plotCtrlDown = false;
      suppressPlotViewClick = false;
      root.addEventListener("pointermove", onPlotPointerMove);
      root.addEventListener("pointerdown", onPlotPointerDown, true);
      root.addEventListener("pointerup", onPlotPointerEnd, true);
      root.addEventListener("pointercancel", onPlotPointerEnd, true);
      root.addEventListener("lostpointercapture", onPlotLostPointerCapture, true);
      root.addEventListener("wheel", onPlotWheel, PLOT_WHEEL_OPTIONS);
      root.addEventListener("dblclick", onPlotDoubleClick, true);
      root.addEventListener("auxclick", onPlotAuxClick, true);
      root.addEventListener("click", onPlotClick, true);
      root.addEventListener("contextmenu", onPlotContextMenu, true);
      root.addEventListener("pointerout", onPlotPointerOut);
      window.addEventListener("keydown", onPlotKeyDown);
      window.addEventListener("keyup", onPlotKeyUp);
      window.addEventListener("blur", onPlotWindowBlur);
      window.addEventListener("resize", scheduleRenderAllPlot1d);

      observedPlots = new Set();
      if (window.ResizeObserver) {
        plotResizeObserver = new ResizeObserver(scheduleRenderAllPlot1d);
      }
      plotMutationObserver = new MutationObserver(function() {
        observePlot1dSizes();
        scheduleRenderAllPlot1d();
      });
      plotMutationObserver.observe(root, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["data-plot", "data-plot-settings"],
      });
      observePlot1dSizes();
      scheduleRenderAllPlot1d();
    }

    function unmountPlotRuntime(root) {
      finishPlotViewDrag();
      suppressPlotViewClick = false;
      plotCtrlDown = false;
      root.removeEventListener("pointermove", onPlotPointerMove);
      root.removeEventListener("pointerdown", onPlotPointerDown, true);
      root.removeEventListener("pointerup", onPlotPointerEnd, true);
      root.removeEventListener("pointercancel", onPlotPointerEnd, true);
      root.removeEventListener("lostpointercapture", onPlotLostPointerCapture, true);
      root.removeEventListener("wheel", onPlotWheel, PLOT_WHEEL_OPTIONS);
      root.removeEventListener("dblclick", onPlotDoubleClick, true);
      root.removeEventListener("auxclick", onPlotAuxClick, true);
      root.removeEventListener("click", onPlotClick, true);
      root.removeEventListener("contextmenu", onPlotContextMenu, true);
      root.removeEventListener("pointerout", onPlotPointerOut);
      window.removeEventListener("keydown", onPlotKeyDown);
      window.removeEventListener("keyup", onPlotKeyUp);
      window.removeEventListener("blur", onPlotWindowBlur);
      window.removeEventListener("resize", scheduleRenderAllPlot1d);
      if (plotMutationObserver) {
        plotMutationObserver.disconnect();
        plotMutationObserver = null;
      }
      if (plotResizeObserver) {
        plotResizeObserver.disconnect();
        plotResizeObserver = null;
      }
      observedPlots.clear();
      if (plotRenderTimer) {
        clearTimeout(plotRenderTimer);
        plotRenderTimer = null;
      }
      hideAllPlotHovers();
      document.body.classList.remove("seurat-plot-panning", "seurat-plot-zooming");
      for (const el of root.querySelectorAll(
        ".seurat-plot1d.is-panning, .seurat-plot1d.is-zooming"
      )) {
        el.classList.remove("is-panning", "is-zooming");
      }
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
      gridVcrState.syncTime = t;
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
        gridVcrState.syncTime = t;
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
          gridVcrState.syncTime = nextTime;
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
      const slider = gridRuntimeElementById("seurat-vcr-step-slider");
      if (slider) {
        const target = getVcrSliderTimeValue(videos || [], plots || []);
        if (Number.isFinite(target)) return target;
      }
      const stateTime = Number(gridVcrState.syncTime);
      if (Number.isFinite(stateTime)) return stateTime;
      const windowTime = Number(gridVcrState.syncTime);
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
            || target.matches(".seurat-plot1d")
            || target.matches(".seurat-dropcell")
          )
        );
      }
      for (const node of Array.from(mutation.addedNodes || [])) {
        if (!node || node.nodeType !== 1) continue;
        if (
          (node.matches && (
            node.matches('img[data-grid-image-sequence="1"]')
            || node.matches('video[data-grid-video="1"]')
            || node.matches(".seurat-plot1d")
            || node.matches(".seurat-dropcell")
          ))
          || (node.querySelector && node.querySelector(
            'img[data-grid-image-sequence="1"], video[data-grid-video="1"], .seurat-plot1d, .seurat-dropcell'
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

    function onGridRuntimeSlider(e) {
      const target = e && e.target;
      if (target && target.id === "seurat-vcr-step-slider") {
        runGridVcrAction("slider");
      }
    }

    function onGridRuntimeClick(e) {
      const target = e && e.target;
      const button = target && target.closest ? target.closest("[data-vcr-action]") : null;
      if (!button || !gridRuntimeRoot || !gridRuntimeRoot.contains(button)) return;
      e.preventDefault();
      runGridVcrAction(button.getAttribute("data-vcr-action") || "");
    }

    function onGridVideoLoadedMetadata(e) {
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
    }

    function onGridVideoEnded(e) {
      const target = e && e.target;
      if (!isGridVideo(target) || !gridVcrState.playing) return;
      const videos = getGridVideos();
      if (!videos.length) return;
      gridVcrState.playing = false;
      stopSyncTimer();
      pauseAllVideos(videos);
      const endTime = getCommonEndTime(videos);
      const t = setAllVideoTimes(
        videos,
        endTime !== null ? endTime : getReferenceTime(videos)
      );
      gridVcrState.syncTime = t;
      updateVcrTimeLabelFromSeconds(t, videos);
    }

    function mediaRuntime() {
      const runtime = window.seuratMediaRuntime;
      return runtime &&
        typeof runtime.mount === "function" &&
        typeof runtime.unmount === "function" &&
        typeof runtime.resetViewForCellIndex === "function"
        ? runtime
        : null;
    }

    function resetGridViewForCellIndex(cellIndex) {
      const idx = Number(cellIndex);
      if (!Number.isInteger(idx) || idx < 0) return;
      const media = mediaRuntime();
      if (media) media.resetViewForCellIndex(idx);
      resetPlotViewForCellIndex(idx);
    }

    function unmountGridRuntime(root) {
      if (!root || root !== gridRuntimeRoot) return;
      unmountPlotRuntime(root);
      const media = mediaRuntime();
      if (media) media.unmount(root);
      root.removeEventListener("input", onGridRuntimeSlider, true);
      root.removeEventListener("change", onGridRuntimeSlider, true);
      root.removeEventListener("click", onGridRuntimeClick);
      root.removeEventListener("loadedmetadata", onGridVideoLoadedMetadata, true);
      root.removeEventListener("ended", onGridVideoEnded, true);
      if (gridMediaObserver) {
        gridMediaObserver.disconnect();
        gridMediaObserver = null;
      }
      if (gridMediaSyncTimer) {
        clearTimeout(gridMediaSyncTimer);
        gridMediaSyncTimer = null;
      }
      stopSyncTimer();
      root.removeAttribute("data-seurat-grid-runtime-owner");
      gridRuntimeRoot = null;
    }

    function mountGridRuntime(root) {
      if (!root || root === gridRuntimeRoot) return;
      if (gridRuntimeRoot) unmountGridRuntime(gridRuntimeRoot);
      gridRuntimeRoot = root;
      root.setAttribute("data-seurat-grid-runtime-owner", "mounted");
      root.addEventListener("input", onGridRuntimeSlider, true);
      root.addEventListener("change", onGridRuntimeSlider, true);
      root.addEventListener("click", onGridRuntimeClick);
      root.addEventListener("loadedmetadata", onGridVideoLoadedMetadata, true);
      root.addEventListener("ended", onGridVideoEnded, true);
      const media = mediaRuntime();
      if (media) {
        media.mount(root, {
          onResetViewRequest: resetGridViewForCellIndex,
        });
      }
      mountPlotRuntime(root);
      gridMediaObserver = new MutationObserver(function(mutations) {
        if ((mutations || []).some(mutationTouchesGridMedia)) {
          scheduleGridMediaSyncToCurrentVcrTime();
        }
      });
      gridMediaObserver.observe(root, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["data-frame-count", "data-frame-indices", "data-frame-sources", "data-time-values", "data-time-mode", "data-plot", "data-plot-settings", "data-timeline-driver"],
      });
      scheduleGridMediaSyncToCurrentVcrTime();
    }

    const runtime = window.seuratGridRuntime || {};
    runtime.mount = mountGridRuntime;
    runtime.unmount = unmountGridRuntime;
    runtime.resetViewForCellIndex = resetGridViewForCellIndex;
    runtime.schedulePlotRender = scheduleRenderAllPlot1d;
    runtime.runVcrAction = runGridVcrAction;
    window.seuratGridRuntime = runtime;
  } catch (err) {
    console.error("seurat client init failed", err);
  }
})();
