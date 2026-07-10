// Local history refresh and path opening
document.addEventListener("click", async function (event) {
      const refreshButton = event.target.closest("[data-refresh-history]");
      if (refreshButton) {
        event.preventDefault();
        const historyKind = refreshButton.dataset.refreshHistory || "single";
        const selector = '[data-history-rail-content="' + historyKind + '"]';
        const railContent = document.querySelector(selector);
        const railPanel = railContent ? railContent.closest(".history-rail-panel") : null;
        if (!railContent) {
          return;
        }

        const oldText = refreshButton.textContent;
        let activeRefreshButton = refreshButton;
        refreshButton.disabled = true;
        refreshButton.textContent = window.seedanceTranslate ? window.seedanceTranslate("refreshing") : "Refreshing...";

        try {
          const response = await fetch("/", { cache: "no-store" });
          const html = await response.text();
          const doc = new DOMParser().parseFromString(html, "text/html");
          const freshContent = doc.querySelector(selector);
          if (freshContent) {
            const freshPanel = freshContent.closest(".history-rail-panel");
            if (railPanel && freshPanel) {
              railPanel.innerHTML = freshPanel.innerHTML;
              activeRefreshButton = railPanel.querySelector('[data-refresh-history="' + historyKind + '"]') || refreshButton;
            } else {
              railContent.innerHTML = freshContent.innerHTML;
            }
            if (window.seedanceInitHistoryPagination) {
              window.seedanceInitHistoryPagination();
            }
            if (window.seedanceSetLanguage) {
              window.seedanceSetLanguage(localStorage.getItem("seedance_gui_language_v1") || "en");
            }
          }
          activeRefreshButton.textContent = window.seedanceTranslate ? window.seedanceTranslate("updated") : "Updated";
          setTimeout(function () {
            activeRefreshButton.textContent = oldText;
          }, 1000);
        } catch (error) {
          activeRefreshButton.textContent = window.seedanceTranslate ? window.seedanceTranslate("refresh_failed") : "Refresh failed";
          setTimeout(function () {
            activeRefreshButton.textContent = oldText;
          }, 1400);
        } finally {
          activeRefreshButton.disabled = false;
        }
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
      link.textContent = window.seedanceTranslate ? window.seedanceTranslate("opening") : "Opening...";

      try {
        await fetch("/open-path?path=" + encodeURIComponent(pathValue), {
          method: "GET",
          cache: "no-store"
        });
        link.textContent = window.seedanceTranslate ? window.seedanceTranslate("opened") : "Opened";
        setTimeout(function () {
          link.textContent = oldText;
        }, 1200);
      } catch (error) {
        link.textContent = window.seedanceTranslate ? window.seedanceTranslate("open_failed") : "Open failed";
        setTimeout(function () {
          link.textContent = oldText;
        }, 1800);
      }
    });
