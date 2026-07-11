document.addEventListener("DOMContentLoaded", function () {
  const config = window.seedanceConfig || {};
  if (!config.autoRefreshEnabled) {
    return;
  }

  const intervalMs = config.historyRefreshIntervalMs || config.refreshIntervalMs || 5000;
  const initialDelayMs = config.historyInitialRefreshDelayMs || Math.min(intervalMs, 600);
  let refreshRunning = false;

  function railNeedsRefresh(historyKind) {
    const content = document.querySelector('[data-history-rail-content="' + historyKind + '"]');
    const panel = content ? content.closest(".history-rail-panel") : null;
    return panel && panel.dataset.historyAutoRefresh === "true";
  }

  async function refreshActiveHistory() {
    if (refreshRunning || typeof window.seedanceRefreshProcessingHistoryCards !== "function") {
      window.setTimeout(refreshActiveHistory, intervalMs);
      return;
    }

    const singleActive = railNeedsRefresh("single");
    const queueActive = railNeedsRefresh("queue");
    if (!singleActive && !queueActive) {
      return;
    }

    refreshRunning = true;
    try {
      if (singleActive) {
        await window.seedanceRefreshProcessingHistoryCards("single");
      }
      if (queueActive) {
        await window.seedanceRefreshProcessingHistoryCards("queue");
      }
    } finally {
      refreshRunning = false;
    }

    if (["single", "queue"].some(railNeedsRefresh)) {
      window.setTimeout(refreshActiveHistory, intervalMs);
    }
  }

  window.setTimeout(refreshActiveHistory, initialDelayMs);
});
