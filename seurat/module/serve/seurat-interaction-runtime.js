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
      dragstart: onDragStart,
      dragend: onDragEnd,
      dragover: onDragOver,
      dragleave: onDragLeave,
      drop: onDrop,
      contextmenu: onContextMenu,
      click: onClick,
    };
  }

  function mount(root) {
    if (!root || mountedRoots.has(root)) return;
    const handlers = createHandlers(root);
    for (const [eventName, handler] of Object.entries(handlers)) {
      root.addEventListener(eventName, handler);
    }
    mountedRoots.set(root, handlers);
    root.setAttribute("data-seurat-interaction-runtime-owner", "mounted");
  }

  function unmount(root) {
    const handlers = root && mountedRoots.get(root);
    if (!root || !handlers) return;
    for (const [eventName, handler] of Object.entries(handlers)) {
      root.removeEventListener(eventName, handler);
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

  const runtime = window.seuratInteractionRuntime || {};
  runtime.mount = mount;
  runtime.unmount = unmount;
  runtime.install = function install(app) {
    app.component("seurat-interaction-runtime", {
      mounted() {
        const root = this.$el.closest(".v-application");
        if (root) window.seuratInteractionRuntime.mount(root);
      },
      beforeUnmount() {
        const root = this.$el.closest(".v-application");
        if (root) window.seuratInteractionRuntime.unmount(root);
      },
      template:
        '<span hidden data-seurat-interaction-runtime="mounted"></span>',
    });
  };

  window.seuratInteractionRuntime = runtime;
})();
