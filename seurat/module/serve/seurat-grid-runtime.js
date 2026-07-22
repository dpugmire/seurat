(function registerSeuratGridRuntime() {
  const seurat = window.seurat = window.seurat || {};
  const runtimes = seurat.runtimes = seurat.runtimes || {};
  const runtime = runtimes.grid || window.seuratGridRuntime || {};

  runtime.install = function install(app) {
    app.component("seurat-grid-runtime", {
      mounted() {
        const root = this.$el.closest(".seurat-content-column");
        if (root && runtime.mount) {
          runtime.mount(root);
        }
      },
      beforeUnmount() {
        const root = this.$el.closest(".seurat-content-column");
        if (root && runtime.unmount) {
          runtime.unmount(root);
        }
      },
      template: '<span hidden data-seurat-grid-runtime="mounted"></span>',
    });
  };

  runtimes.grid = runtime;
  window.seuratGridRuntime = runtime;
})();
