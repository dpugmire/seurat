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

        function updateVcrTimeLabelFromSeconds(rawSeconds, videos) {
          const label = document.getElementById("catnip-vcr-time-value");
          const seconds = Number(rawSeconds);
          const safeSeconds = Number.isFinite(seconds) && seconds >= 0 ? seconds : 0;
          const fps = inferFpsForVideos(videos);
          const frameCounter = safeSeconds * fps;
          if (label) {
            label.textContent = "Time = " + frameCounter.toFixed(6);
          }

          const slider = document.getElementById("catnip-vcr-step-slider");
          if (!slider) return;

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

          const frameValue = Math.round(frameCounter);
          const clamped = Math.max(0, Math.min(frameValue, maxFrames));
          slider.value = String(clamped);
        }

        // Always expose a VCR handler, even when drag/drop was initialized
        // in an older page session.
        window.catnipGridVcr = function(action) {
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
            setAllTime(getVcrSliderFrameValue() / fps);
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
        };

        function getGridVideos() {
          return Array.from(document.querySelectorAll('video[data-grid-video="1"]'));
        }

        function isGridVideo(target) {
          return !!(target && target.matches && target.matches('video[data-grid-video="1"]'));
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
          let t = Number(rawTime);
          if (!Number.isFinite(t) || t < 0) {
            t = 0;
          }
          const commonEnd = getCommonEndTime(videos);
          if (commonEnd !== null) {
            t = Math.min(t, commonEnd);
          }
          return t;
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

        function inferFrameStepSeconds(videos) {
          const fps = inferFpsForVideos(videos);
          return 1.0 / fps;
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
            if (videosNow.length) {
              updateVcrTimeLabelFromSeconds(getReferenceTime(videosNow), videosNow);
            } else {
              updateVcrTimeLabelFromSeconds(0, []);
            }
            return;
          }

          const videos = getGridVideos();
          if (!videos.length) {
            gridVcrState.playing = false;
            stopSyncTimer();
            updateVcrTimeLabelFromSeconds(0, []);
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
          if (!videos.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const base = clampTimeForVideos(
            Number.isFinite(gridVcrState.syncTime) ? gridVcrState.syncTime : getReferenceTime(videos),
            videos
          );
          const next = setAllVideoTimes(videos, base + deltaSeconds);
          gridVcrState.syncTime = next;
          updateVcrTimeLabelFromSeconds(next, videos);
          if (gridVcrState.playing) {
            playAllVideos(videos);
            startSyncTimer();
          } else {
            pauseAllVideos(videos);
          }
        }

        function stepAllVideosByFrames(frameCount) {
          const videos = getGridVideos();
          if (!videos.length) return;
          const frameStep = inferFrameStepSeconds(videos);
          seekAllVideosBy(frameStep * Number(frameCount || 0));
        }

        function seekAllVideosToSlider() {
          const videos = getGridVideos();
          if (!videos.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const fps = inferFpsForVideos(videos);
          const targetSeconds = getVcrSliderFrameValue() / fps;
          const t = setAllVideoTimes(videos, targetSeconds);
          gridVcrState.syncTime = t;
          updateVcrTimeLabelFromSeconds(t, videos);
          if (gridVcrState.playing) {
            playAllVideos(videos);
            startSyncTimer();
          } else {
            pauseAllVideos(videos);
          }
        }

        function setAllToStart() {
          const videos = getGridVideos();
          if (!videos.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const t = setAllVideoTimes(videos, 0);
          gridVcrState.syncTime = t;
          updateVcrTimeLabelFromSeconds(t, videos);
          if (gridVcrState.playing) {
            playAllVideos(videos);
            startSyncTimer();
          } else {
            pauseAllVideos(videos);
          }
        }

        function setAllToEnd() {
          const videos = getGridVideos();
          if (!videos.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const commonEnd = getCommonEndTime(videos);
          const target = commonEnd !== null ? commonEnd : getReferenceTime(videos);
          const t = setAllVideoTimes(videos, target);
          gridVcrState.syncTime = t;
          updateVcrTimeLabelFromSeconds(t, videos);
          if (gridVcrState.playing) {
            playAllVideos(videos);
            startSyncTimer();
          } else {
            pauseAllVideos(videos);
          }
        }

        function playAllFromSyncTime() {
          const videos = getGridVideos();
          if (!videos.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          const base = setAllVideoTimes(
            videos,
            Number.isFinite(gridVcrState.syncTime) ? gridVcrState.syncTime : getReferenceTime(videos)
          );
          gridVcrState.syncTime = base;
          updateVcrTimeLabelFromSeconds(base, videos);
          gridVcrState.playing = true;
          playAllVideos(videos);
          startSyncTimer();
        }

        function pauseAllAtCurrentTime() {
          const videos = getGridVideos();
          if (!videos.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          gridVcrState.syncTime = clampTimeForVideos(getReferenceTime(videos), videos);
          gridVcrState.playing = false;
          stopSyncTimer();
          pauseAllVideos(videos);
          updateVcrTimeLabelFromSeconds(gridVcrState.syncTime, videos);
        }

        function stopAllVideos() {
          const videos = getGridVideos();
          if (!videos.length) {
            updateVcrTimeLabelFromSeconds(0, []);
            return;
          }
          gridVcrState.playing = false;
          stopSyncTimer();
          pauseAllVideos(videos);
          gridVcrState.syncTime = setAllVideoTimes(videos, 0);
          updateVcrTimeLabelFromSeconds(gridVcrState.syncTime, videos);
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
                .catnip-dropcell { transition: background 0.15s, box-shadow 0.15s; }
                .catnip-drop-hover {
                  background: #e3f2fd !important;
                  box-shadow: inset 0 0 0 2px #1976d2 !important;
                }
                .catnip-vcr-bar {
                  display: flex;
                  align-items: center;
                  gap: 12px;
                  flex-wrap: wrap;
                  width: 100%;
                  min-height: 28px;
                  margin: 0 0 8px 0;
                }
                .catnip-vcr-controls {
                  display: flex;
                  align-items: center;
                  gap: 6px;
                }
                .catnip-vcr-btn,
                .catnip-vcr-bar button[data-vcr-action],
                .catnip-grid-layout-btn {
                  min-width: 34px;
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
                .catnip-vcr-btn:hover,
                .catnip-vcr-bar button[data-vcr-action]:hover,
                .catnip-grid-layout-btn:hover:not(:disabled) {
                  background: #f2f2f2;
                }
                .catnip-vcr-btn:disabled,
                .catnip-vcr-bar button[data-vcr-action]:disabled,
                .catnip-grid-layout-btn:disabled {
                  opacity: 0.45;
                  cursor: not-allowed;
                }
                .catnip-vcr-time {
                  min-width: 170px;
                  text-align: center;
                }
                .catnip-vcr-slider {
                  width: 220px;
                  cursor: pointer;
                }
                .catnip-grid-layout-controls {
                  margin-left: auto;
                  display: flex;
                  flex-direction: column;
                  align-items: flex-end;
                  gap: 4px;
                }
                .catnip-grid-layout-buttons {
                  display: flex;
                  align-items: center;
                  gap: 6px;
                }
                .catnip-grid-layout-label {
                  min-width: 44px;
                  text-align: center;
                  color: #555;
                }
                .catnip-grid-size-controls {
                  display: flex;
                  align-items: center;
                  gap: 6px;
                  min-width: 190px;
                }
                .catnip-grid-size-slider {
                  flex: 1 1 auto;
                  min-width: 120px;
                }
                .catnip-grid-size-label {
                  min-width: 48px;
                  text-align: right;
                  color: #555;
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
                        with vuetify.VCard(variant="outlined", style="flex:1 1 auto; min-height:0;"):
                            with vuetify.VCardText(style="height:100%; overflow:auto;"):
                                with html.Div(classes="catnip-vcr-bar"):
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
                                        with html.Div(classes="catnip-grid-size-controls"):
                                            vuetify.VSlider(
                                                v_model=("gridCellSize",),
                                                min=160,
                                                max=520,
                                                step=20,
                                                density="compact",
                                                hide_details=True,
                                                class_="catnip-grid-size-slider",
                                                title="Grid cell size",
                                            )
                                            html.Span(
                                                "{{ gridCellSize + 'px' }}",
                                                class_="text-caption catnip-grid-size-label",
                                            )
                                        with html.Div(classes="catnip-grid-layout-buttons"):
                                            html.Span(
                                                "{{ gridRows + 'x' + gridCols }}",
                                                class_="text-caption catnip-grid-layout-label",
                                            )
                                            html.Button(
                                                "+ Row",
                                                classes="catnip-grid-layout-btn",
                                                click=ctrl.add_grid_row,
                                                raw_attrs=[
                                                    'type="button"',
                                                    ':disabled="gridRows >= gridMaxRows"',
                                                ],
                                                title="Add row",
                                            )
                                            html.Button(
                                                "- Row",
                                                classes="catnip-grid-layout-btn",
                                                click=ctrl.delete_grid_row,
                                                raw_attrs=[
                                                    'type="button"',
                                                    ':disabled="gridRows <= gridMinRows"',
                                                ],
                                                title="Delete active row or last row",
                                            )
                                            html.Button(
                                                "+ Col",
                                                classes="catnip-grid-layout-btn",
                                                click=ctrl.add_grid_column,
                                                raw_attrs=[
                                                    'type="button"',
                                                    ':disabled="gridCols >= gridMaxCols"',
                                                ],
                                                title="Add column",
                                            )
                                            html.Button(
                                                "- Col",
                                                classes="catnip-grid-layout-btn",
                                                click=ctrl.delete_grid_column,
                                                raw_attrs=[
                                                    'type="button"',
                                                    ':disabled="gridCols <= gridMinCols"',
                                                ],
                                                title="Delete active column or last column",
                                            )
                                with html.Div(
                                    style=(
                                        "('display:grid;'"
                                        " + 'grid-template-columns:repeat(' + gridCols + ', ' + Number(gridCellSize || 300) + 'px);'"
                                        " + 'grid-template-rows:repeat(' + gridRows + ', ' + (Number(gridCellSize || 300) + 32) + 'px);'"
                                        " + 'width:max-content;'"
                                        " + 'margin:0 auto;'"
                                        " + 'justify-content:center;'"
                                        " + 'align-content:start;'"
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
                                                "('width:' + Number(gridCellSize || 300) + 'px; height:' + (Number(gridCellSize || 300) + 32) + 'px; overflow:hidden; cursor:pointer; display:flex; flex-direction:column;'"
                                                " + (((i % gridCols) !== (gridCols - 1)) ? 'border-right:1px solid #cfcfcf;' : '')"
                                                " + ((i < ((gridRows - 1) * gridCols)) ? 'border-bottom:1px solid #cfcfcf;' : '')"
                                                " + ((activeGridCell === i) ? 'background:#eef5ff; box-shadow: inset 0 0 0 2px #1e88e5;' : ''))",
                                            ),
                                        ):
                                            with vuetify.Template(v_if="tile && tile.variable_name"):
                                                with html.Div(
                                                    style=(
                                                        "display:flex;"
                                                        "align-items:center;"
                                                        "gap:8px;"
                                                        "width:100%;"
                                                        "height:32px;"
                                                        "padding:4px 6px;"
                                                        "background:#7bd0ef;"
                                                        "border-bottom:1px solid #3ca7c9;"
                                                    ),
                                                ):
                                                    html.Div(
                                                        "{{ tile.variable_name || 'variable' }}",
                                                        style="flex:1; min-width:0; font-size:0.9rem; font-weight:400; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;",
                                                    )
                                                    html.Button(
                                                        "x",
                                                        classes="catnip-cell-close",
                                                        click=(ctrl.clear_grid_cell, "[i]"),
                                                        style=(
                                                            "margin-left:auto;"
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
                                                    style=(
                                                        "('width:' + Number(gridCellSize || 300) + 'px; height:' + Number(gridCellSize || 300) + 'px; background:#111;')",
                                                    ),
                                                ):
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
                                                                "('height:' + Number(gridCellSize || 300) + 'px;"
                                                                "display:flex;"
                                                                "align-items:center;"
                                                                "justify-content:center;"
                                                                "text-align:center;"
                                                                "padding:8px;"
                                                                "color:#ddd;')"
                                                            ),
                                                        )
                                            with vuetify.Template(v_if="!(tile && tile.variable_name)"):
                                                html.Div(
                                                    "Drop variable here",
                                                    class_="text-caption",
                                                    style=(
                                                        "height:100%;"
                                                        "display:flex;"
                                                        "align-items:center;"
                                                        "justify-content:center;"
                                                        "color:#777;"
                                                    ),
                                                )

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
                                        html.Div("{{ detailsSelectedVar ? ('Sources: ' + detailsSelectedVar) : 'Sources' }}")
                                        vuetify.VSpacer()
                                        vuetify.VBtn("Close", variant="text", size="small", click=ctrl.toggle_sources)

                                with vuetify.VCardText():
                                    with vuetify.Template(v_if="detailsSelectedVar"):
                                        html.Div("{{ 'Selected source: ' + selectedSourceLabel }}", class_="text-caption mb-2")
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
                                                            click=(ctrl.select_source, "[r._key]"),
                                                        ):
                                                            with html.Td(style="text-align:center; white-space:nowrap;"):
                                                                html.Input(
                                                                    type="radio",
                                                                    name="selected-source",
                                                                    checked=("((selectedSourceKeys || []).includes(r._key))",),
                                                                    click=(ctrl.select_source, "[r._key]"),
                                                                )
                                                            html.Td(
                                                                "{{ r.source_dataset || [r.producer, r.casename, r.file].filter(Boolean).join('/') }}",
                                                                style="white-space:nowrap;",
                                                            )
                                                            html.Td("{{ r.min }}", style="white-space:nowrap;")
                                                            html.Td("{{ r.max }}", style="white-space:nowrap;")
                                        with vuetify.Template(v_if="!detailsSelectedVar"):
                                            html.Div("Select a variable first.", class_="text-caption")

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
                    with vuetify.Template(v_if="(contextMenuCellVisualizationOptions || []).length"):
                        html.Div("Visualization Type", classes="menu-section")
                        with vuetify.Template(v_for="vis in contextMenuCellVisualizationOptions", key="vis"):
                            html.Div(
                                "{{ ((vis === contextMenuCellSelectedVisualization) ? '✓ ' : '') + vis }}",
                                classes="menu-item",
                                click=(ctrl.context_menu_cell_pick_visualization, "[vis]"),
                            )

    return layout
