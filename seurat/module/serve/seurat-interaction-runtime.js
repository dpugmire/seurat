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
    let workspaceTabDrag = null;
    let tabOverflowFrame = 0;
    let tabOverflowMutationObserver = null;
    const visibleWorkspaceTabs = new WeakMap();
    const tabOverflowResizeObserver =
      typeof ResizeObserver === "function"
        ? new ResizeObserver(scheduleWorkspaceTabOverflowUpdate)
        : null;

    function updateWorkspaceTabOverflow() {
      tabOverflowFrame = 0;
      for (const viewport of root.querySelectorAll(
        ".seurat-workspace-tabs-viewport"
      )) {
        const tabs = viewport.querySelector(".seurat-workspace-tabs");
        if (!tabs) continue;
        if (tabOverflowResizeObserver) tabOverflowResizeObserver.observe(tabs);
        const activeTab = tabs.querySelector(
          ".seurat-workspace-tab.is-pane-tab-active"
        );
        const activeTabId = activeTab
          ? activeTab.getAttribute("data-tab-id") || ""
          : "";
        if (activeTabId && visibleWorkspaceTabs.get(viewport) !== activeTabId) {
          const shell = activeTab.closest(".seurat-workspace-tab-shell");
          if (shell) {
            const tabsRect = tabs.getBoundingClientRect();
            const shellRect = shell.getBoundingClientRect();
            const shellLeft = tabs.scrollLeft + shellRect.left - tabsRect.left;
            const shellRight = shellLeft + shellRect.width;
            if (shellLeft < tabs.scrollLeft) tabs.scrollLeft = shellLeft;
            else if (shellRight > tabs.scrollLeft + tabs.clientWidth) {
              tabs.scrollLeft = shellRight - tabs.clientWidth;
            }
          }
          visibleWorkspaceTabs.set(viewport, activeTabId);
        }
        const maximum = Math.max(0, tabs.scrollWidth - tabs.clientWidth);
        viewport.classList.toggle("has-overflow-left", tabs.scrollLeft > 1);
        viewport.classList.toggle(
          "has-overflow-right",
          maximum > 1 && tabs.scrollLeft < maximum - 1
        );
      }
    }

    function scheduleWorkspaceTabOverflowUpdate() {
      if (tabOverflowFrame) return;
      tabOverflowFrame = window.requestAnimationFrame(
        updateWorkspaceTabOverflow
      );
    }

    function onWorkspaceTabsScroll(event) {
      const target = event && event.target;
      if (target && target.classList.contains("seurat-workspace-tabs")) {
        scheduleWorkspaceTabOverflowUpdate();
      }
    }

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
      scheduleWorkspaceTabOverflowUpdate();
    }

    function clearWorkspaceTabDropMarkers() {
      for (const shell of root.querySelectorAll(
        ".seurat-workspace-tab-shell.is-tab-drop-before, " +
          ".seurat-workspace-tab-shell.is-tab-drop-after"
      )) {
        shell.classList.remove("is-tab-drop-before", "is-tab-drop-after");
      }
    }

    function finishWorkspaceTabDrag() {
      clearWorkspaceTabDropMarkers();
      for (const tab of root.querySelectorAll(
        ".seurat-workspace-tab[aria-grabbed='true']"
      )) {
        tab.removeAttribute("aria-grabbed");
      }
      for (const shell of root.querySelectorAll(
        ".seurat-workspace-tab-shell.is-tab-dragging"
      )) {
        shell.classList.remove("is-tab-dragging");
      }
      workspaceTabDrag = null;
    }

    function updateWorkspaceTabDropTarget(event) {
      if (!workspaceTabDrag) return false;
      const target = event && event.target;
      const tabs = closestWithinRoot(target, ".seurat-workspace-tabs", root);
      clearWorkspaceTabDropMarkers();
      workspaceTabDrag.insertionIndex = null;
      if (
        !tabs ||
        (tabs.getAttribute("data-pane-id") || "") !== workspaceTabDrag.paneId
      ) {
        return false;
      }

      const shells = Array.from(
        tabs.querySelectorAll(".seurat-workspace-tab-shell")
      );
      const targetShell = closestWithinRoot(
        target,
        ".seurat-workspace-tab-shell",
        tabs
      );
      if (targetShell) {
        const targetIndex = shells.indexOf(targetShell);
        if (targetIndex < 0) return false;
        const bounds = targetShell.getBoundingClientRect();
        const before = (Number(event.clientX) || 0) < bounds.left + bounds.width / 2;
        targetShell.classList.add(
          before ? "is-tab-drop-before" : "is-tab-drop-after"
        );
        workspaceTabDrag.insertionIndex = targetIndex + (before ? 0 : 1);
      } else {
        const lastShell = shells[shells.length - 1];
        if (lastShell) lastShell.classList.add("is-tab-drop-after");
        workspaceTabDrag.insertionIndex = shells.length;
      }
      return true;
    }

    function onDragStart(event) {
      const target = event && event.target;
      if (!event.dataTransfer) return;

      const workspaceTab = closestWithinRoot(
        target,
        ".seurat-workspace-tab",
        root
      );
      if (workspaceTab) {
        const paneId = workspaceTab.getAttribute("data-pane-id") || "";
        const tabId = workspaceTab.getAttribute("data-tab-id") || "";
        const shell = workspaceTab.closest(".seurat-workspace-tab-shell");
        if (!paneId || !tabId || !shell) return;
        finishWorkspaceTabDrag();
        workspaceTabDrag = { paneId, tabId, insertionIndex: null };
        workspaceTab.setAttribute("aria-grabbed", "true");
        shell.classList.add("is-tab-dragging");
        event.dataTransfer.setData(
          "application/x-seurat-workspace-tab",
          tabId
        );
        event.dataTransfer.effectAllowed = "move";
        return;
      }

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
      if (cell.closest(".seurat-workspace-grid-preview")) return;
      const filled = cell.getAttribute("data-cell-filled");
      const fromIndex = cell.getAttribute("data-cell-index");
      if (filled !== "1" || fromIndex === null) return;
      event.dataTransfer.setData("application/x-seurat-grid-cell", fromIndex);
      event.dataTransfer.effectAllowed = "move";
      cell.style.opacity = "0.55";
    }

    function onDragEnd(event) {
      const target = event && event.target;
      if (
        workspaceTabDrag ||
        closestWithinRoot(target, ".seurat-workspace-tab", root)
      ) {
        finishWorkspaceTabDrag();
        return;
      }
      const variable = closestWithinRoot(target, ".seurat-draggable-var", root);
      if (variable) variable.style.opacity = "1";
      const cell = closestWithinRoot(target, ".seurat-dropcell", root);
      if (cell) cell.style.opacity = "1";
    }

    function onDragOver(event) {
      if (workspaceTabDrag) {
        if (updateWorkspaceTabDropTarget(event)) {
          event.preventDefault();
          if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
        }
        return;
      }
      const cell = closestWithinRoot(
        event && event.target,
        ".seurat-dropcell",
        root
      );
      if (!cell) return;
      if (cell.closest(".seurat-workspace-grid-preview")) return;
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
      if (workspaceTabDrag) {
        const accepted = updateWorkspaceTabDropTarget(event);
        const paneId = workspaceTabDrag.paneId;
        const tabId = workspaceTabDrag.tabId;
        const insertionIndex = workspaceTabDrag.insertionIndex;
        if (accepted) event.preventDefault();
        finishWorkspaceTabDrag();
        if (accepted && Number.isInteger(insertionIndex)) {
          trameTrigger("reorder_workspace_tab_trigger", [
            paneId,
            tabId,
            insertionIndex,
          ]);
        }
        return;
      }
      const cell = closestWithinRoot(
        event && event.target,
        ".seurat-dropcell",
        root
      );
      if (!cell) return;
      if (cell.closest(".seurat-workspace-grid-preview")) return;
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

      const workspaceTab = closestWithinRoot(
        target,
        ".seurat-workspace-tab",
        root
      );
      if (workspaceTab) {
        event.preventDefault();
        const paneId = workspaceTab.getAttribute("data-pane-id") || "";
        const tabId = workspaceTab.getAttribute("data-tab-id") || "";
        if (paneId && tabId) {
          trameTrigger("show_tab_context_menu", [
            paneId,
            tabId,
            event.clientX || 0,
            event.clientY || 0,
          ]);
        }
        return;
      }

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
        if (cell.closest(".seurat-workspace-grid-preview")) return;
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

    const handlers = {
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
        scroll: onWorkspaceTabsScroll,
      },
      window: {
        resize: onWindowResize,
      },
      cleanup() {
        finishFloatingDrag();
        finishWorkspaceTabDrag();
        if (tabOverflowFrame) {
          window.cancelAnimationFrame(tabOverflowFrame);
          tabOverflowFrame = 0;
        }
        if (tabOverflowMutationObserver) {
          tabOverflowMutationObserver.disconnect();
          tabOverflowMutationObserver = null;
        }
        if (tabOverflowResizeObserver) tabOverflowResizeObserver.disconnect();
        for (const panel of root.querySelectorAll(
          ".seurat-floating-options-panel.is-dragging"
        )) {
          panel.classList.remove("is-dragging");
        }
      },
    };

    if (typeof MutationObserver === "function") {
      tabOverflowMutationObserver = new MutationObserver(
        scheduleWorkspaceTabOverflowUpdate
      );
      tabOverflowMutationObserver.observe(root, {
        attributes: true,
        attributeFilter: ["class"],
        childList: true,
        subtree: true,
      });
    }
    scheduleWorkspaceTabOverflowUpdate();

    return handlers;
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
