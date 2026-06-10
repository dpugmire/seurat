from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import client, html
from trame.widgets import vuetify3 as vuetify


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
          if (videos.length) {
            return getVcrSliderFrameValue() / inferFpsForVideos(videos);
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
          const bounds = (typeof getMediaTimelineBounds === "function")
            ? getMediaTimelineBounds(videos, plots)
            : { start: 0, end: 0, usesVideos: !!(videos && videos.length) };
          const label = document.getElementById("catnip-vcr-time-value");
          const seconds = Number(rawSeconds);
          const safeSeconds = (typeof clampTimeForMedia === "function")
            ? clampTimeForMedia(seconds, videos, plots)
            : (Number.isFinite(seconds) && seconds >= 0 ? seconds : 0);
          const fps = inferFpsForVideos(videos);
          if (label) {
            if (videos && videos.length) {
              label.textContent = "Time = " + (safeSeconds * fps).toFixed(6);
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

          if (videos && videos.length) {
            let minDuration = Infinity;
            for (const v of (videos || [])) {
              const d = Number(v && v.duration);
              if (Number.isFinite(d) && d > 0) {
                minDuration = Math.min(minDuration, d);
              }
            }
            let maxFrames = 1;
            if (Number.isFinite(minDuration)) {
              maxFrames = Math.max(1, Math.round(Math.max(0, minDuration - 0.04) * fps));
            }
            slider.min = "0";
            slider.max = String(maxFrames);
            slider.step = "1";

            const frameValue = Math.round(safeSeconds * fps);
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

        if (window.__catnipDnDInit) return;
        window.__catnipDnDInit = true;
        const gridVcrState = {
          playing: false,
          syncTime: 0,
          syncTimer: null,
          lastTickMs: 0,
        };

        setupPlot1dObserver();

        function getGridVideos() {
          return Array.from(document.querySelectorAll('video[data-grid-video="1"]'));
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

        function renderPlot1d(el) {
          const plot = parsePlotData(el);
          const settings = normalizePlotSettings(parsePlotSettings(el));
          const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 0, height: 0 };
          const width = Math.max(240, Math.round(rect.width || el.clientWidth || 300));
          const height = Math.max(180, Math.round(rect.height || el.clientHeight || 300));
          const renderKey = String(el.__catnipPlotRaw || "") + "|" + String(el.__catnipPlotSettingsRaw || "") + "|" + width + "x" + height;
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
          const xAxis = resolvePlotAxis(plot, series, settings, "x");
          const yAxis = resolvePlotAxis(plot, series, settings, "y");
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
            dataXMin,
            dataXMax,
            sx,
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
          const videoEnd = getCommonEndTime(videos || []);
          if (videoEnd !== null) {
            return { start: 0, end: videoEnd, usesVideos: true };
          }
          const plotBounds = getPlotTimelineBounds(plots || getGridPlots());
          if (plotBounds) {
            return { start: plotBounds.start, end: plotBounds.end, usesVideos: false };
          }
          return { start: 0, end: 0, usesVideos: false };
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
          const progress = bounds.usesVideos ? ((t - bounds.start) / denom) : null;
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
          const shiftActive = !!(event.shiftKey || window.__catnipPlotShiftDown);
          if (!meta || !meta.hoverGroup || !meta.hoverTip || !shiftActive) {
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
          window.__catnipPlotShiftDown = false;

          document.addEventListener("keydown", function(e) {
            if (e && e.key === "Shift") {
              window.__catnipPlotShiftDown = true;
            }
          });
          document.addEventListener("keyup", function(e) {
            if (e && e.key === "Shift") {
              window.__catnipPlotShiftDown = false;
              hideAllPlotHovers();
            }
          });
          window.addEventListener("blur", function() {
            window.__catnipPlotShiftDown = false;
            hideAllPlotHovers();
          });
          document.addEventListener("pointermove", function(e) {
            const target = e && e.target;
            const el = target && target.closest ? target.closest(".catnip-plot1d") : null;
            if (!el) return;
            const shiftActive = !!(e.shiftKey || window.__catnipPlotShiftDown);
            if (!shiftActive) {
              hidePlotHover(el);
              return;
            }
            updatePlotHover(el, e);
          });
          document.addEventListener("pointerout", function(e) {
            const target = e && e.target;
            const el = target && target.closest ? target.closest(".catnip-plot1d") : null;
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

        function setupPlot1dObserver() {
          setupPlotHoverHandlers();
          if (window.__catnipPlotObserverInit) return;
          window.__catnipPlotObserverInit = true;
          const observer = new MutationObserver(function() {
            scheduleRenderAllPlot1d();
          });
          observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-plot", "data-plot-settings"] });
          window.addEventListener("resize", scheduleRenderAllPlot1d);
          scheduleRenderAllPlot1d();
        }

        function getCommonEndTime(videos) {
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

        function stopSyncTimer() {
          if (gridVcrState.syncTimer) {
            clearInterval(gridVcrState.syncTimer);
            gridVcrState.syncTimer = null;
          }
        }

        function syncGridVideosNow() {
          if (!gridVcrState.playing) {
            stopSyncTimer();
            const videosNow = getGridVideos();
            const plotsNow = getGridPlots();
            if (videosNow.length) {
              updateVcrTimeLabelFromSeconds(getReferenceTime(videosNow), videosNow);
            } else if (plotsNow.length) {
              updateVcrTimeLabelFromSeconds(gridVcrState.syncTime, [], plotsNow);
            } else {
              updateVcrTimeLabelFromSeconds(0, []);
            }
            return;
          }

          const videos = getGridVideos();
          const plots = getGridPlots();
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

        function seekAllVideosBy(deltaSeconds) {
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
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
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!videos.length && !plots.length) return;
          const frameStep = inferFrameStepSeconds(videos, plots);
          seekAllVideosBy(frameStep * Number(frameCount || 0));
        }

        function seekAllVideosToSlider() {
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const targetSeconds = getVcrSliderTimeValue(videos, plots);
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
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
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
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
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
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
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
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          gridVcrState.syncTime = clampTimeForMedia(videos.length ? getReferenceTime(videos) : gridVcrState.syncTime, videos, plots);
          gridVcrState.playing = false;
          stopSyncTimer();
          pauseAllVideos(videos);
          updateVcrTimeLabelFromSeconds(gridVcrState.syncTime, videos, plots);
        }

        function stopAllVideos() {
          const videos = getGridVideos();
          const plots = getGridPlots();
          if (!videos.length && !plots.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          gridVcrState.playing = false;
          stopSyncTimer();
          pauseAllVideos(videos);
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
                  font-size: 11px;
                  font-weight: 800;
                  letter-spacing: 0.05em;
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
                .catnip-var-group-chevron {
                  width: 12px;
                  text-align: center;
                  font-family: monospace;
                  font-size: 12px;
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
                .catnip-dropcell { transition: background 0.15s, outline-color 0.15s; }
                .catnip-plot1d {
                  position: relative;
                  overflow: hidden;
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
                .catnip-drop-hover {
                  background: #e3f2fd !important;
                  box-shadow: inset 0 0 0 2px #1976d2 !important;
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
                  width: 28px;
                  padding: 0;
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
            with vuetify.VContainer(fluid=True, class_="pa-2"):
                with vuetify.VRow():
                    with vuetify.VCol(cols=2, style="display:flex; flex-direction:column; height:80vh;"):
                        with vuetify.VCard(
                            variant="outlined",
                            style="flex:1 1 auto; min-height:0; display:flex; flex-direction:column;",
                        ):
                            with vuetify.VCardTitle():
                                html.Div("Variables")
                            with vuetify.VCardText(style="flex:1 1 auto; min-height:0; overflow-y:auto;"):
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
                                            with html.Div(
                                                class_="catnip-var-group-title",
                                                click=(ctrl.toggle_variable_group, "[group.name]"),
                                                style="font-weight:800;",
                                            ):
                                                html.Span(
                                                    "{{ (variableGroupCollapsed && variableGroupCollapsed[group.name]) ? '+' : '-' }}",
                                                    class_="catnip-var-group-chevron",
                                                )
                                                html.Span("{{ group.name }}")
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

                    with vuetify.VCol(cols=10, style="display:flex; flex-direction:column; height:80vh;"):
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
                                                "onclick=\"window.catnipGridVcr && window.catnipGridVcr('start'); return false;\"",
                                            ],
                                            title="Jump to start",
                                        )
                                        html.Button(
                                            "<<",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="back"',
                                                "onclick=\"window.catnipGridVcr && window.catnipGridVcr('back'); return false;\"",
                                            ],
                                            title="Back step",
                                        )
                                        html.Button(
                                            "▶",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="play"',
                                                "onclick=\"window.catnipGridVcr && window.catnipGridVcr('play'); return false;\"",
                                            ],
                                            title="Play all",
                                        )
                                        html.Button(
                                            "⏸",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="pause"',
                                                "onclick=\"window.catnipGridVcr && window.catnipGridVcr('pause'); return false;\"",
                                            ],
                                            title="Pause all",
                                        )
                                        html.Button(
                                            "⏹",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="stop"',
                                                "onclick=\"window.catnipGridVcr && window.catnipGridVcr('stop'); return false;\"",
                                            ],
                                            title="Stop and reset",
                                        )
                                        html.Button(
                                            ">>",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="forward"',
                                                "onclick=\"window.catnipGridVcr && window.catnipGridVcr('forward'); return false;\"",
                                            ],
                                            title="Forward step",
                                        )
                                        html.Button(
                                            ">|",
                                            classes="catnip-vcr-btn",
                                            raw_attrs=[
                                                'type="button"',
                                                'data-vcr-action="end"',
                                                "onclick=\"window.catnipGridVcr && window.catnipGridVcr('end'); return false;\"",
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
                                                                                html.Button("-", classes="catnip-grid-layout-btn", click=ctrl.delete_grid_row, raw_attrs=['type="button"', ':disabled="gridRows <= gridMinRows"'], title="Delete active row or last row")
                                                                                html.Span("{{ gridRows }}", class_="text-caption text-center")
                                                                                html.Button("+", classes="catnip-grid-layout-btn", click=ctrl.add_grid_row, raw_attrs=['type="button"', ':disabled="gridRows >= gridMaxRows"'], title="Add row")
                                                                            with html.Div(classes="catnip-grid-layout-stepper"):
                                                                                html.Span("Cols", class_="text-caption catnip-grid-layout-stepper-label")
                                                                                html.Button("-", classes="catnip-grid-layout-btn", click=ctrl.delete_grid_column, raw_attrs=['type="button"', ':disabled="gridCols <= gridMinCols"'], title="Delete active column or last column")
                                                                                html.Span("{{ gridCols }}", class_="text-caption text-center")
                                                                                html.Button("+", classes="catnip-grid-layout-btn", click=ctrl.add_grid_column, raw_attrs=['type="button"', ':disabled="gridCols >= gridMaxCols"'], title="Add column")
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
                                with vuetify.Template(v_if="scalarPlotStatus"):
                                    html.Div("{{ scalarPlotStatus }}", class_="text-caption mb-2", style="color:#8a4b00;")
                                with html.Div(
                                    style=(
                                        "('display:grid;'"
                                        " + ((gridSizingMode === 'fit')"
                                        " ? ('grid-template-columns:repeat(' + gridCols + ', minmax(' + Number(gridFitMinCellSize || 180) + 'px, 1fr));'"
                                        " + 'grid-template-rows:repeat(' + gridRows + ', minmax(' + (Number(gridFitMinCellSize || 180) + 32) + 'px, 1fr));'"
                                        " + 'justify-content:stretch;'"
                                        " + 'align-content:stretch;')"
                                        " : ('grid-template-columns:repeat(' + gridCols + ', ' + Number(gridCellSize || 300) + 'px);'"
                                        " + 'grid-template-rows:repeat(' + gridRows + ', ' + (Number(gridCellSize || 300) + 32) + 'px);'"
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
                                                "[i, (($event && $event.target && $event.target.closest && $event.target.closest('.catnip-cell-close')) ? 1 : 0)]",
                                            ),
                                            classes="catnip-dropcell",
                                            raw_attrs=[
                                                ':data-cell-index="i"',
                                                ':data-cell-filled="((tile && tile.variable_name) ? 1 : 0)"',
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
                                                " : ('width:' + Number(gridCellSize || 300) + 'px; height:' + (Number(gridCellSize || 300) + 32) + 'px;')))"
                                                " + 'overflow:hidden; cursor:pointer; display:flex; flex-direction:column; position:relative; box-sizing:border-box;'"
                                                " + ((gridLayoutMode === 'spanning') ? 'border:1px solid #cfcfcf;' : ('border-left:1px solid #cfcfcf; border-top:1px solid #cfcfcf;'"
                                                " + (((i % gridCols) === (gridCols - 1)) ? 'border-right:1px solid #cfcfcf;' : '')"
                                                " + ((i >= ((gridRows - 1) * gridCols)) ? 'border-bottom:1px solid #cfcfcf;' : '')))"
                                                " + ((activeGridCell === i) ? 'background:#e7f0ff; outline:3px solid #0d47a1; outline-offset:-3px; z-index:2;' : '')"
                                                " + ((gridLayoutMode === 'spanning' && tile && tile.grid_hidden) ? 'display:none;' : '')",
                                            ),
                                        ):
                                            with vuetify.Template(v_if="tile && tile.variable_name"):
                                                with html.Div(
                                                    style=(
                                                        "('display:flex;'"
                                                        " + 'align-items:center;'"
                                                        " + 'gap:8px;'"
                                                        " + 'width:100%;'"
                                                        " + 'height:32px;'"
                                                        " + 'padding:4px 6px;'"
                                                        " + ((activeGridCell === i) ? 'background:#1565c0; color:#fff; border-bottom:1px solid #0d47a1;' : 'background:#7bd0ef; color:#111; border-bottom:1px solid #3ca7c9;'))",
                                                    ),
                                                ):
                                                    html.Div(
                                                        "{{ tile.display_title || tile.variable_name || 'variable' }}",
                                                        style="flex:1 1 auto; min-width:0; font-size:0.9rem; font-weight:400; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;",
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
                                                            with vuetify.Template(v_if="tile.media_type === 'image'"):
                                                                html.Img(
                                                                    src=("tile.src",),
                                                                    style=(
                                                                        "display:block;"
                                                                        "width:100%;"
                                                                        "height:100%;"
                                                                        "object-fit:contain;"
                                                                        "background:#111;"
                                                                    ),
                                                                )
                                                            with vuetify.Template(v_if="tile.media_type !== 'image'"):
                                                                html.Video(
                                                                    src=("tile.src",),
                                                                    class_="catnip-grid-video",
                                                                    controls=False,
                                                                    autoplay=False,
                                                                    loop=False,
                                                                    muted=True,
                                                                    raw_attrs=['data-grid-video="1"', "playsinline", "webkit-playsinline"],
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
                                        html.Div(
                                            "{{ detailsSelectedVar ? (((sourceDialogMode === 'add') ? 'Add Source: ' : 'Sources: ') + detailsSelectedVar) : 'Sources' }}"
                                        )
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
                                                "Sources:",
                                                class_="text-caption",
                                                style="white-space:nowrap;",
                                            )
                                            vuetify.VTextField(
                                                v_model=("sourceFilterDraftText",),
                                                placeholder='e.g. "F0.0179" in sourceName',
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
                                                                "{{ r.source_dataset || [r.producer, r.casename, r.file].filter(Boolean).join('/') }}",
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

                        with vuetify.VDialog(v_model=("showPlotSettingsModal",), max_width="760"):
                            with vuetify.VCard():
                                with vuetify.VCardTitle():
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div("{{ 'Plot Settings: ' + (plotSettingsTitle || '') }}")
                                        vuetify.VSpacer()
                                        vuetify.VBtn("Close", variant="text", size="small", click=ctrl.cancel_plot_settings)

                                with vuetify.VCardText():
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
                                    vuetify.VSpacer()
                                    vuetify.VBtn("Reset", variant="text", click=ctrl.reset_plot_settings)
                                    vuetify.VBtn("Cancel", variant="text", click=ctrl.cancel_plot_settings)
                                    vuetify.VBtn("Apply", variant="tonal", click=ctrl.apply_plot_settings)

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
                    with vuetify.Template(v_if="(contextMenuCellVisualizationOptions || []).length"):
                        html.Div("Visualization Type", classes="menu-section")
                        with vuetify.Template(v_for="vis in contextMenuCellVisualizationOptions", key="vis"):
                            html.Div(
                                "{{ ((vis === contextMenuCellSelectedVisualization) ? '✓ ' : '') + vis }}",
                                classes="menu-item",
                                click=(ctrl.context_menu_cell_pick_visualization, "[vis]"),
                            )

    return layout
