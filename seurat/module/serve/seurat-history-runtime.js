(function registerSeuratHistoryRuntime() {
  const mountedRoots = new WeakMap();

  function trameTrigger(name) {
    if (window.trame && window.trame.trigger) window.trame.trigger(name, []);
  }

  function isEditable(target) {
    if (!target || !target.closest) return false;
    // Range controls retain focus after timeline scrubbing, but they do not
    // have a native text-edit history that workspace undo must preserve.
    if (target.closest("input[type='range']")) return false;
    return !!target.closest(
      "input, textarea, select, [contenteditable='true'], [contenteditable='']"
    );
  }

  function mount(root) {
    if (!root || mountedRoots.has(root)) return;
    const onKeyDown = (event) => {
      if (!event || event.defaultPrevented || event.altKey || isEditable(event.target)) {
        return;
      }
      const modifier = event.ctrlKey || event.metaKey;
      if (!modifier) return;
      const key = String(event.key || "").toLowerCase();
      const redo = (key === "z" && event.shiftKey) || (key === "y" && !event.shiftKey);
      const undo = key === "z" && !event.shiftKey;
      if (!undo && !redo) return;
      event.preventDefault();
      trameTrigger(redo ? "redo_workspace_trigger" : "undo_workspace_trigger");
    };
    const ownerWindow = root.ownerDocument && root.ownerDocument.defaultView;
    if (!ownerWindow) return;
    ownerWindow.addEventListener("keydown", onKeyDown, true);
    mountedRoots.set(root, { onKeyDown, ownerWindow });
    root.setAttribute("data-seurat-history-runtime-owner", "mounted");
  }

  function unmount(root) {
    const mounted = root && mountedRoots.get(root);
    if (!root || !mounted) return;
    mounted.ownerWindow.removeEventListener("keydown", mounted.onKeyDown, true);
    mountedRoots.delete(root);
    root.removeAttribute("data-seurat-history-runtime-owner");
  }

  const seurat = window.seurat = window.seurat || {};
  const runtimes = seurat.runtimes = seurat.runtimes || {};
  const runtime = runtimes.history || window.seuratHistoryRuntime || {};
  runtime.mount = mount;
  runtime.unmount = unmount;
  runtime.install = function install(app) {
    app.component("seurat-history-runtime", {
      mounted() {
        const root = this.$el.closest(".v-application");
        if (root) runtime.mount(root);
      },
      beforeUnmount() {
        const root = this.$el.closest(".v-application");
        if (root) runtime.unmount(root);
      },
      template: '<span hidden data-seurat-history-runtime="mounted"></span>',
    });
  };

  runtimes.history = runtime;
  window.seuratHistoryRuntime = runtime;
})();
