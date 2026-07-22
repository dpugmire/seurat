(function initSeuratMediaRuntime() {
  "use strict";

  const PAN_ZOOM_MIN_SCALE = 0.25;
  const PAN_ZOOM_MAX_SCALE = 8;
  const PAN_ZOOM_WHEEL_OPTIONS = { capture: true, passive: false };

  let runtimeRoot = null;
  let onResetViewRequest = null;
  let panZoomDrag = null;
  let suppressPanZoomClick = false;
  let resetViewObserver = null;
  let resetViewRequestElement = null;
  let lastResetViewRequest = "";

  function runtimeBody() {
    const ownerDocument = runtimeRoot && runtimeRoot.ownerDocument;
    return ownerDocument ? ownerDocument.body : document.body;
  }

  function panZoomContent(viewport) {
    if (!viewport || !viewport.children) return null;
    for (const child of viewport.children) {
      if (child.classList && child.classList.contains("seurat-panzoom-content")) {
        return child;
      }
    }
    return viewport.querySelector
      ? viewport.querySelector(".seurat-panzoom-content")
      : null;
  }

  function panZoomState(viewport) {
    if (!viewport.__seuratPanZoomState) {
      viewport.__seuratPanZoomState = { scale: 1, tx: 0, ty: 0 };
    }
    return viewport.__seuratPanZoomState;
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
    content.style.transform =
      "translate(" +
      state.tx.toFixed(2) +
      "px, " +
      state.ty.toFixed(2) +
      "px) scale(" +
      state.scale.toFixed(6) +
      ")";
    viewport.classList.toggle(
      "is-panzoomed",
      Math.abs(state.scale - 1) > 1e-6 ||
        Math.abs(state.tx) > 0.5 ||
        Math.abs(state.ty) > 0.5
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
    if (!Number.isInteger(idx) || idx < 0 || !runtimeRoot) return;
    const cell = runtimeRoot.querySelector(
      '.seurat-dropcell[data-cell-index="' + String(idx) + '"]'
    );
    if (!cell) return;
    const viewports = cell.querySelectorAll
      ? cell.querySelectorAll(".seurat-panzoom-viewport")
      : [];
    for (const viewport of viewports) {
      resetPanZoom(viewport);
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

  function panZoomViewportFromEvent(event) {
    const target = event && event.target;
    const viewport =
      target && target.closest
        ? target.closest(".seurat-panzoom-viewport")
        : null;
    if (
      !viewport ||
      !runtimeRoot ||
      !runtimeRoot.contains(viewport) ||
      target.closest(".seurat-grid-track-resize-handle")
    ) {
      return null;
    }
    return viewport;
  }

  function releasePanZoomPointerCapture(drag) {
    if (!drag || !drag.viewport || drag.pointerId === undefined) return;
    try {
      if (
        !drag.viewport.hasPointerCapture ||
        drag.viewport.hasPointerCapture(drag.pointerId)
      ) {
        drag.viewport.releasePointerCapture(drag.pointerId);
      }
    } catch (_) {
      // The pointer may already have been released by the browser.
    }
  }

  function onPanZoomPointerDown(event) {
    const viewport = panZoomViewportFromEvent(event);
    if (!viewport) return;
    const isShiftPan = event.button === 0 && event.shiftKey;
    const isMiddleZoom = event.button === 1;
    if (!isShiftPan && !isMiddleZoom) return;

    finishPanZoomDrag();
    panZoomDrag = {
      viewport,
      mode: isMiddleZoom ? "zoom" : "pan",
      startX: Number(event.clientX) || 0,
      startY: Number(event.clientY) || 0,
      base: Object.assign({}, panZoomState(viewport)),
      pointerId: event.pointerId,
      moved: false,
    };
    viewport.classList.add(isMiddleZoom ? "is-zooming" : "is-panning");
    runtimeBody().classList.add(
      isMiddleZoom ? "seurat-panzoom-zooming" : "seurat-panzoom-panning"
    );
    try {
      viewport.setPointerCapture(event.pointerId);
    } catch (_) {
      // Pointer capture is best-effort for older browser implementations.
    }
    event.preventDefault();
    event.stopPropagation();
  }

  function onPanZoomPointerMove(event) {
    if (!panZoomDrag) return;
    if (
      panZoomDrag.pointerId !== undefined &&
      event.pointerId !== panZoomDrag.pointerId
    ) {
      return;
    }
    const dx = (Number(event.clientX) || 0) - panZoomDrag.startX;
    const dy = (Number(event.clientY) || 0) - panZoomDrag.startY;
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
    event.preventDefault();
    event.stopPropagation();
  }

  function finishPanZoomDrag(event) {
    if (!panZoomDrag) return;
    const current = panZoomDrag;
    panZoomDrag = null;
    current.viewport.classList.remove("is-panning", "is-zooming");
    runtimeBody().classList.remove(
      "seurat-panzoom-panning",
      "seurat-panzoom-zooming"
    );
    suppressPanZoomClick = !!current.moved;
    releasePanZoomPointerCapture(current);
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
  }

  function onPanZoomPointerEnd(event) {
    if (
      panZoomDrag &&
      (panZoomDrag.pointerId === undefined ||
        event.pointerId === panZoomDrag.pointerId)
    ) {
      finishPanZoomDrag(event);
    }
  }

  function onPanZoomLostPointerCapture(event) {
    if (panZoomDrag && event.target === panZoomDrag.viewport) {
      finishPanZoomDrag();
    }
  }

  function onPanZoomWheel(event) {
    const viewport = panZoomViewportFromEvent(event);
    if (!viewport) return;
    const factor = Math.exp(-(Number(event.deltaY) || 0) * 0.0015);
    zoomPanZoomAt(viewport, event.clientX, event.clientY, factor);
    event.preventDefault();
    event.stopPropagation();
  }

  function onPanZoomDoubleClick(event) {
    const viewport = panZoomViewportFromEvent(event);
    if (!viewport) return;
    resetPanZoom(viewport);
    event.preventDefault();
    event.stopPropagation();
  }

  function onPanZoomDragStart(event) {
    const viewport = panZoomViewportFromEvent(event);
    if (viewport && (panZoomDrag || event.shiftKey)) {
      event.preventDefault();
      event.stopPropagation();
    }
  }

  function onPanZoomAuxClick(event) {
    const viewport = panZoomViewportFromEvent(event);
    if (viewport && event.button === 1) {
      event.preventDefault();
      event.stopPropagation();
    }
  }

  function onPanZoomClick(event) {
    if (!suppressPanZoomClick) return;
    suppressPanZoomClick = false;
    const viewport = panZoomViewportFromEvent(event);
    if (!viewport) return;
    event.preventDefault();
    event.stopPropagation();
  }

  function handleResetViewRequest(raw) {
    const text = String(raw || "");
    if (!text || text === lastResetViewRequest) return;
    lastResetViewRequest = text;
    try {
      const request = JSON.parse(text);
      const cellIndex = request && request.cell_index;
      if (onResetViewRequest) {
        onResetViewRequest(cellIndex);
      } else {
        resetPanZoomForCellIndex(cellIndex);
      }
    } catch (_err) {
      // Ignore malformed transient reset requests.
    }
  }

  function scanResetViewRequest() {
    if (!resetViewRequestElement) return;
    handleResetViewRequest(
      resetViewRequestElement.getAttribute("data-reset-view-request") || ""
    );
  }

  function unmountPanZoomRuntime(root) {
    if (!root || root !== runtimeRoot) return;
    finishPanZoomDrag();
    suppressPanZoomClick = false;
    root.removeEventListener("pointerdown", onPanZoomPointerDown, true);
    root.removeEventListener("pointermove", onPanZoomPointerMove, true);
    root.removeEventListener("pointerup", onPanZoomPointerEnd, true);
    root.removeEventListener("pointercancel", onPanZoomPointerEnd, true);
    root.removeEventListener(
      "lostpointercapture",
      onPanZoomLostPointerCapture,
      true
    );
    root.removeEventListener("wheel", onPanZoomWheel, PAN_ZOOM_WHEEL_OPTIONS);
    root.removeEventListener("dblclick", onPanZoomDoubleClick, true);
    root.removeEventListener("dragstart", onPanZoomDragStart, true);
    root.removeEventListener("auxclick", onPanZoomAuxClick, true);
    root.removeEventListener("click", onPanZoomClick, true);
    if (resetViewObserver) {
      resetViewObserver.disconnect();
      resetViewObserver = null;
    }
    resetViewRequestElement = null;
    lastResetViewRequest = "";
    onResetViewRequest = null;
    runtimeBody().classList.remove(
      "seurat-panzoom-panning",
      "seurat-panzoom-zooming"
    );
    for (const viewport of root.querySelectorAll(
      ".seurat-panzoom-viewport.is-panning, .seurat-panzoom-viewport.is-zooming"
    )) {
      viewport.classList.remove("is-panning", "is-zooming");
    }
    root.removeAttribute("data-seurat-media-runtime-owner");
    runtimeRoot = null;
  }

  function mountPanZoomRuntime(root, options) {
    if (!root) return;
    if (root === runtimeRoot) {
      onResetViewRequest =
        options && typeof options.onResetViewRequest === "function"
          ? options.onResetViewRequest
          : null;
      return;
    }
    if (runtimeRoot) unmountPanZoomRuntime(runtimeRoot);

    runtimeRoot = root;
    onResetViewRequest =
      options && typeof options.onResetViewRequest === "function"
        ? options.onResetViewRequest
        : null;
    root.setAttribute("data-seurat-media-runtime-owner", "mounted");
    root.addEventListener("pointerdown", onPanZoomPointerDown, true);
    root.addEventListener("pointermove", onPanZoomPointerMove, true);
    root.addEventListener("pointerup", onPanZoomPointerEnd, true);
    root.addEventListener("pointercancel", onPanZoomPointerEnd, true);
    root.addEventListener(
      "lostpointercapture",
      onPanZoomLostPointerCapture,
      true
    );
    root.addEventListener("wheel", onPanZoomWheel, PAN_ZOOM_WHEEL_OPTIONS);
    root.addEventListener("dblclick", onPanZoomDoubleClick, true);
    root.addEventListener("dragstart", onPanZoomDragStart, true);
    root.addEventListener("auxclick", onPanZoomAuxClick, true);
    root.addEventListener("click", onPanZoomClick, true);

    lastResetViewRequest = "";
    resetViewRequestElement = root.querySelector("#seurat-reset-view-request");
    if (resetViewRequestElement) {
      resetViewObserver = new MutationObserver(scanResetViewRequest);
      resetViewObserver.observe(resetViewRequestElement, {
        attributes: true,
        attributeFilter: ["data-reset-view-request"],
      });
      scanResetViewRequest();
    }
  }

  const seurat = window.seurat = window.seurat || {};
  const runtimes = seurat.runtimes = seurat.runtimes || {};
  const runtime = runtimes.media || window.seuratMediaRuntime || {};
  runtime.mount = mountPanZoomRuntime;
  runtime.unmount = unmountPanZoomRuntime;
  runtime.resetViewForCellIndex = resetPanZoomForCellIndex;
  runtimes.media = runtime;
  window.seuratMediaRuntime = runtime;
})();
