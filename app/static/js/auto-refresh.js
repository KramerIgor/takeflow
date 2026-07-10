// Auto refresh is limited to queue work so Single Generation prompt text is not lost.
(function () {
  const config = window.seedanceConfig || {};
  if (!config.autoRefreshEnabled) {
    return;
  }

  setTimeout(function () {
    const activeTab = localStorage.getItem("seedance_gui_active_tab_v1") || "project-settings";
    const refreshTabs = new Set(["queue-workflow"]);
    if (!refreshTabs.has(activeTab)) {
      return;
    }
    if (window.location.pathname === "/") {
      window.location.reload();
    } else {
      window.location.replace("/");
    }
  }, config.refreshIntervalMs || 15000);
})();
