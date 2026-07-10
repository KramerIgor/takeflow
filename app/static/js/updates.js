document.addEventListener("DOMContentLoaded", function () {
  const panel = document.querySelector("[data-update-panel]");
  if (!panel) {
    return;
  }

  const summary = panel.querySelector("[data-update-summary]");
  const checkButton = panel.querySelector("[data-check-updates]");
  const downloadButton = panel.querySelector("[data-download-update]");
  const launchButton = panel.querySelector("[data-launch-update]");
  const progress = panel.querySelector("[data-update-progress]");
  const progressBar = panel.querySelector("[data-update-progress-bar]");
  const progressLabel = panel.querySelector("[data-update-progress-label]");

  let progressTimer = null;

  function translate(key, fallback) {
    if (typeof window.seedanceTranslate === "function") {
      return window.seedanceTranslate(key);
    }
    return fallback;
  }

  function tokenBody() {
    const body = new URLSearchParams();
    body.set("token", (window.seedanceConfig && window.seedanceConfig.shutdownToken) || "");
    return body;
  }

  function showPanel() {
    panel.hidden = false;
  }

  function setSummary(text) {
    if (summary) {
      summary.textContent = text;
    }
  }

  function renderUpdateState(state) {
    if (!state) {
      return;
    }
    if (state.available) {
      showPanel();
      setSummary(
        translate("update_available", "New version available") +
          ": v" +
          (state.latest_display_version || state.latest_version)
      );
      if (downloadButton) {
        downloadButton.hidden = false;
      }
    } else if (state.checking) {
      showPanel();
      setSummary(translate("update_checking", "Checking for updates..."));
    } else if (state.error) {
      showPanel();
      setSummary(translate("update_check_failed", "Update check failed") + ": " + state.error);
    } else if (panel.hidden === false) {
      setSummary(translate("update_current", "Takeflow is up to date."));
    }
  }

  function renderDownloadState(state) {
    if (!state) {
      return;
    }
    if (state.active || state.complete || state.error) {
      showPanel();
      progress.hidden = false;
    }
    const percent = Number.isFinite(state.percent) ? Math.max(0, Math.min(100, state.percent)) : 0;
    if (progressBar) {
      progressBar.style.width = percent + "%";
    }
    if (state.active) {
      progressLabel.textContent = translate("download_progress", "Downloading") + ": " + Math.round(percent) + "%";
      return;
    }
    if (state.complete) {
      progressLabel.textContent = translate("download_complete", "Download complete.");
      if (launchButton) {
        launchButton.hidden = false;
      }
      if (downloadButton) {
        downloadButton.hidden = true;
      }
      return;
    }
    if (state.error) {
      progressLabel.textContent = translate("download_failed", "Download failed") + ": " + state.error;
    }
  }

  async function refreshUpdateState() {
    const response = await fetch("/update-status", { cache: "no-store" });
    renderUpdateState(await response.json());
  }

  async function pollDownload() {
    const response = await fetch("/update-download/status", { cache: "no-store" });
    const state = await response.json();
    renderDownloadState(state);
    if (!state.active && progressTimer) {
      window.clearInterval(progressTimer);
      progressTimer = null;
    }
  }

  if (checkButton) {
    checkButton.addEventListener("click", async function () {
      checkButton.disabled = true;
      setSummary(translate("update_checking", "Checking for updates..."));
      showPanel();
      try {
        const response = await fetch("/check-updates", { method: "POST" });
        renderUpdateState(await response.json());
      } finally {
        checkButton.disabled = false;
      }
    });
  }

  if (downloadButton) {
    downloadButton.addEventListener("click", async function () {
      downloadButton.disabled = true;
      progress.hidden = false;
      progressLabel.textContent = translate("download_starting", "Starting download...");
      const response = await fetch("/update-download/start", {
        method: "POST",
        body: tokenBody()
      });
      renderDownloadState(await response.json());
      if (!progressTimer) {
        progressTimer = window.setInterval(pollDownload, 700);
      }
    });
  }

  if (launchButton) {
    launchButton.addEventListener("click", async function () {
      const ok = typeof window.seedanceConfirmAction === "function"
        ? await window.seedanceConfirmAction("confirm_install_update")
        : window.confirm(translate("confirm_install_update", "Launch installer and shut down Takeflow?"));
      if (!ok) {
        return;
      }
      launchButton.disabled = true;
      launchButton.textContent = translate("launching_installer", "Launching...");
      await fetch("/update-launch-installer", {
        method: "POST",
        body: tokenBody()
      });
    });
  }

  refreshUpdateState().catch(function () {});
});
