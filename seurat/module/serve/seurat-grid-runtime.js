(function registerSeuratGridRuntime() {
  const runtime = window.seuratGridRuntime || {};

  runtime.install = function install(app) {
    app.component("seurat-grid-runtime", {
      mounted() {
        const root = this.$el.closest(".seurat-content-column");
        if (root && window.seuratGridRuntime && window.seuratGridRuntime.mount) {
          window.seuratGridRuntime.mount(root);
        }
      },
      beforeUnmount() {
        const root = this.$el.closest(".seurat-content-column");
        if (root && window.seuratGridRuntime && window.seuratGridRuntime.unmount) {
          window.seuratGridRuntime.unmount(root);
        }
      },
      template: '<span hidden data-seurat-grid-runtime="mounted"></span>',
    });
  };

  window.seuratGridRuntime = runtime;
})();
