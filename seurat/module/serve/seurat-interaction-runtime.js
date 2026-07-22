(function registerSeuratInteractionRuntime() {
  const mountedRoots = new WeakMap();

  function trameTrigger(name, args) {
    if (window.trame && window.trame.trigger) {
      window.trame.trigger(name, args || []);
    }
  }

  function closestWithinRoot(target, selector, root) {
    if (!target || !target.closest) return null;
    const element = target.closest(selector);
    return element && root.contains(element) ? element : null;
  }

  function createHandlers(root) {
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

    function releasePointerCapture(drag) {
      if (!drag || !drag.handle || drag.pointerId === undefined) return;
      try {
        if (
          !drag.handle.hasPointerCapture ||
          drag.handle.hasPointerCapture(drag.pointerId)
        ) {
          drag.handle.releasePointerCapture(drag.pointerId);
        }
      } catch (_) {
        // The pointer may already have been released by the browser.
      }
    }

    function finishFloatingDrag() {
      if (!floatingDrag) return;
      const current = floatingDrag;
      floatingDrag = null;
      current.panel.classList.remove("is-dragging");
      releasePointerCapture(current);
    }

    function onPointerDown(event) {
      if (event.button !== undefined && event.button !== 0) return;
      const handle = closestWithinRoot(
        event && event.target,
        ".seurat-floating-panel-drag-handle",
        root
      );
      if (!handle) return;
      const panel = closestWithinRoot(handle, ".seurat-floating-options-panel", root);
      if (!panel) return;
      finishFloatingDrag();
      const rect = panel.getBoundingClientRect();
      floatingDrag = {
        panel,
        handle,
        pointerId: event.pointerId,
        startX: Number(event.clientX) || 0,
        startY: Number(event.clientY) || 0,
        left: rect.left,
        top: rect.top,
      };
      panel.classList.add("is-dragging");
      try {
        handle.setPointerCapture(event.pointerId);
      } catch (_) {
        // Pointer capture is best-effort for older browser implementations.
      }
      event.preventDefault();
    }

    function onPointerMove(event) {
      if (!floatingDrag) return;
      if (
        floatingDrag.pointerId !== undefined &&
        event.pointerId !== floatingDrag.pointerId
      ) {
        return;
      }
      const dx = (Number(event.clientX) || 0) - floatingDrag.startX;
      const dy = (Number(event.clientY) || 0) - floatingDrag.startY;
      const position = clampFloatingPanel(
        floatingDrag.panel,
        floatingDrag.left + dx,
        floatingDrag.top + dy
      );
      floatingDrag.panel.style.left = position.left + "px";
      floatingDrag.panel.style.top = position.top + "px";
      event.preventDefault();
    }

    function onPointerEnd(event) {
      if (
        floatingDrag &&
        (floatingDrag.pointerId === undefined ||
          event.pointerId === floatingDrag.pointerId)
      ) {
        finishFloatingDrag();
      }
    }

    function onLostPointerCapture(event) {
      if (floatingDrag && event.target === floatingDrag.handle) {
        finishFloatingDrag();
      }
    }

    function onWindowResize() {
      for (const panel of root.querySelectorAll(".seurat-floating-options-panel")) {
        const rect = panel.getBoundingClientRect();
        const position = clampFloatingPanel(panel, rect.left, rect.top);
        panel.style.left = position.left + "px";
        panel.style.top = position.top + "px";
      }
    }

    function onDragStart(event) {
      const target = event && event.target;
      if (!event.dataTransfer) return;

      const variable = closestWithinRoot(target, ".seurat-draggable-var", root);
      if (variable) {
        const item = variable.getAttribute("data-item") || "";
        if (!item) return;
        event.dataTransfer.setData("text/plain", item);
        event.dataTransfer.setData("application/x-seurat-var", item);
        event.dataTransfer.effectAllowed = "copy";
        variable.style.opacity = "0.45";
        return;
      }

      const cell = closestWithinRoot(target, ".seurat-dropcell", root);
      if (!cell) return;
      const filled = cell.getAttribute("data-cell-filled");
      const fromIndex = cell.getAttribute("data-cell-index");
      if (filled !== "1" || fromIndex === null) return;
      event.dataTransfer.setData("application/x-seurat-grid-cell", fromIndex);
      event.dataTransfer.effectAllowed = "move";
      cell.style.opacity = "0.55";
    }

    function onDragEnd(event) {
      const target = event && event.target;
      const variable = closestWithinRoot(target, ".seurat-draggable-var", root);
      if (variable) variable.style.opacity = "1";
      const cell = closestWithinRoot(target, ".seurat-dropcell", root);
      if (cell) cell.style.opacity = "1";
    }

    function onDragOver(event) {
      const cell = closestWithinRoot(
        event && event.target,
        ".seurat-dropcell",
        root
      );
      if (!cell) return;
      event.preventDefault();
      if (event.dataTransfer) {
        const types = Array.from(event.dataTransfer.types || []);
        event.dataTransfer.dropEffect = types.includes(
          "application/x-seurat-grid-cell"
        )
          ? "move"
          : "copy";
      }
      cell.classList.add("seurat-drop-hover");
    }

    function onDragLeave(event) {
      const cell = closestWithinRoot(
        event && event.target,
        ".seurat-dropcell",
        root
      );
      if (cell && !cell.contains(event.relatedTarget)) {
        cell.classList.remove("seurat-drop-hover");
      }
    }

    function onDrop(event) {
      const cell = closestWithinRoot(
        event && event.target,
        ".seurat-dropcell",
        root
      );
      if (!cell) return;
      event.preventDefault();
      cell.classList.remove("seurat-drop-hover");

      const fromCell = event.dataTransfer
        ? event.dataTransfer.getData("application/x-seurat-grid-cell") || ""
        : "";
      const targetIndex = cell.getAttribute("data-cell-index");
      if (fromCell !== "" && targetIndex !== null) {
        trameTrigger("move_grid_cell_trigger", [fromCell, targetIndex]);
        return;
      }

      const item = event.dataTransfer
        ? event.dataTransfer.getData("text/plain") ||
          event.dataTransfer.getData("application/x-seurat-var") ||
          ""
        : "";
      if (item && targetIndex !== null) {
        trameTrigger("assign_var_to_grid_cell_trigger", [item, targetIndex]);
      }
    }

    function onContextMenu(event) {
      const target = event && event.target;
      if (closestWithinRoot(target, "#seurat-context-menu", root)) return;

      const variable = closestWithinRoot(target, ".seurat-draggable-var", root);
      if (variable) {
        event.preventDefault();
        const item = variable.getAttribute("data-item") || "";
        if (item) {
          trameTrigger("show_item_context_menu", [
            item,
            event.clientX || 0,
            event.clientY || 0,
          ]);
        }
        return;
      }

      const cell = closestWithinRoot(target, ".seurat-dropcell", root);
      if (cell) {
        event.preventDefault();
        const index = cell.getAttribute("data-cell-index");
        if (index !== null) {
          trameTrigger("show_cell_context_menu", [
            index,
            event.clientX || 0,
            event.clientY || 0,
          ]);
        }
        return;
      }

      trameTrigger("hide_context_menu_trigger", []);
    }

    function onClick(event) {
      if (!closestWithinRoot(event && event.target, "#seurat-context-menu", root)) {
        trameTrigger("hide_context_menu_trigger", []);
      }
    }

    return {
      root: {
        dragstart: onDragStart,
        dragend: onDragEnd,
        dragover: onDragOver,
        dragleave: onDragLeave,
        drop: onDrop,
        contextmenu: onContextMenu,
        click: onClick,
      },
      capture: {
        pointerdown: onPointerDown,
        pointermove: onPointerMove,
        pointerup: onPointerEnd,
        pointercancel: onPointerEnd,
        lostpointercapture: onLostPointerCapture,
      },
      window: {
        resize: onWindowResize,
      },
      cleanup() {
        finishFloatingDrag();
        for (const panel of root.querySelectorAll(
          ".seurat-floating-options-panel.is-dragging"
        )) {
          panel.classList.remove("is-dragging");
        }
      },
    };
  }

  function mount(root) {
    if (!root || mountedRoots.has(root)) return;
    const handlers = createHandlers(root);
    for (const [eventName, handler] of Object.entries(handlers.root)) {
      root.addEventListener(eventName, handler);
    }
    for (const [eventName, handler] of Object.entries(handlers.capture)) {
      root.addEventListener(eventName, handler, true);
    }
    for (const [eventName, handler] of Object.entries(handlers.window)) {
      window.addEventListener(eventName, handler);
    }
    mountedRoots.set(root, handlers);
    root.setAttribute("data-seurat-interaction-runtime-owner", "mounted");
  }

  function unmount(root) {
    const handlers = root && mountedRoots.get(root);
    if (!root || !handlers) return;
    handlers.cleanup();
    for (const [eventName, handler] of Object.entries(handlers.root)) {
      root.removeEventListener(eventName, handler);
    }
    for (const [eventName, handler] of Object.entries(handlers.capture)) {
      root.removeEventListener(eventName, handler, true);
    }
    for (const [eventName, handler] of Object.entries(handlers.window)) {
      window.removeEventListener(eventName, handler);
    }
    for (const element of root.querySelectorAll(
      ".seurat-draggable-var, .seurat-dropcell"
    )) {
      element.style.opacity = "1";
    }
    for (const cell of root.querySelectorAll(".seurat-drop-hover")) {
      cell.classList.remove("seurat-drop-hover");
    }
    mountedRoots.delete(root);
    root.removeAttribute("data-seurat-interaction-runtime-owner");
  }

  const seurat = window.seurat = window.seurat || {};
  const runtimes = seurat.runtimes = seurat.runtimes || {};
  const runtime = runtimes.interaction || window.seuratInteractionRuntime || {};
  runtime.mount = mount;
  runtime.unmount = unmount;
  runtime.install = function install(app) {
    app.component("seurat-interaction-runtime", {
      mounted() {
        const root = this.$el.closest(".v-application");
        if (root) runtime.mount(root);
      },
      beforeUnmount() {
        const root = this.$el.closest(".v-application");
        if (root) runtime.unmount(root);
      },
      template:
        '<span hidden data-seurat-interaction-runtime="mounted"></span>',
    });
  };

  runtimes.interaction = runtime;
  window.seuratInteractionRuntime = runtime;
})();
