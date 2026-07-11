function translate(key, fallback) {
  return typeof window.seedanceTranslate === "function" ? window.seedanceTranslate(key) : fallback;
}

async function refreshHistoryRail(historyKind, options = {}) {
  const selector = '[data-history-rail-content="' + historyKind + '"]';
  const railContent = document.querySelector(selector);
  const railPanel = railContent ? railContent.closest(".history-rail-panel") : null;
  if (!railContent || !railPanel) {
    return false;
  }

  const feedbackButton = options.feedbackButton || null;
  if (feedbackButton) {
    feedbackButton.disabled = true;
    feedbackButton.textContent = translate("refreshing", "Refreshing...");
  }

  try {
    const response = await fetch("/", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("History refresh failed with HTTP " + response.status);
    }

    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, "text/html");
    const freshContent = doc.querySelector(selector);
    const freshPanel = freshContent ? freshContent.closest(".history-rail-panel") : null;
    if (!freshPanel) {
      throw new Error("History rail was not present in the response");
    }

    railPanel.innerHTML = freshPanel.innerHTML;
    railPanel.dataset.historyAutoRefresh = freshPanel.dataset.historyAutoRefresh || "false";

    if (window.seedanceInitHistoryPagination) {
      window.seedanceInitHistoryPagination();
    }
    if (window.seedanceSetLanguage) {
      window.seedanceSetLanguage(localStorage.getItem("seedance_gui_language_v1") || "en");
    }

    const activeButton = railPanel.querySelector('[data-refresh-history="' + historyKind + '"]');
    if (feedbackButton && activeButton) {
      activeButton.textContent = translate("updated", "Updated");
      setTimeout(function () {
        activeButton.textContent = translate("refresh_history", "Refresh");
      }, 1000);
    }

    document.dispatchEvent(new CustomEvent("seedance:history-refreshed", {
      detail: { historyKind }
    }));
    return true;
  } catch (error) {
    if (feedbackButton && feedbackButton.isConnected) {
      feedbackButton.textContent = translate("refresh_failed", "Refresh failed");
      setTimeout(function () {
        feedbackButton.textContent = translate("refresh_history", "Refresh");
        feedbackButton.disabled = false;
      }, 1400);
    }
    return false;
  }
}

window.seedanceRefreshHistoryRail = refreshHistoryRail;

document.addEventListener("click", async function (event) {
  const refreshButton = event.target.closest("[data-refresh-history]");
  if (refreshButton) {
    event.preventDefault();
    await refreshHistoryRail(refreshButton.dataset.refreshHistory || "single", {
      feedbackButton: refreshButton
    });
    return;
  }

  const link = event.target.closest(".open-path-link");
  if (!link) {
    return;
  }

  event.preventDefault();
  const pathValue = link.dataset.openPath;
  if (!pathValue) {
    return;
  }

  const oldText = link.textContent;
  link.textContent = translate("opening", "Opening...");

  try {
    const response = await fetch("/open-path?path=" + encodeURIComponent(pathValue), {
      method: "GET",
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error("Open path failed with HTTP " + response.status);
    }
    link.textContent = translate("opened", "Opened");
    setTimeout(function () {
      link.textContent = oldText;
    }, 1200);
  } catch (error) {
    link.textContent = translate("open_failed", "Open failed");
    setTimeout(function () {
      link.textContent = oldText;
    }, 1800);
  }
});
