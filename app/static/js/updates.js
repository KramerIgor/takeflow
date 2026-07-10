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

  function setSummary(text) {
    if (summary) {
      summary.textContent = text;
    }
  }

  function setState(name) {
    panel.dataset.state = name;
  }

  function showOnly(button) {
    [checkButton, downloadButton, launchButton].forEach(function (candidate) {
      if (candidate) {
        candidate.hidden = candidate !== button;
      }
    });
  }

  function renderUpdateState(state) {
    if (!state) {
      return;
    }
    if (state.available) {
      setState("available");
      setSummary(translate("update_available", "Update available"));
      showOnly(downloadButton);
    } else if (state.checking) {
      setState("checking");
      setSummary(translate("update_checking", "Checking..."));
      showOnly(checkButton);
    } else if (state.error) {
      setState("error");
      setSummary(translate("update_check_failed", "Unable to connect"));
      showOnly(checkButton);
    } else {
      setState("current");
      setSummary(translate("update_current", "Latest release"));
      showOnly(checkButton);
    }
  }

  function renderDownloadState(state) {
    if (!state) {
      return;
    }
    progress.hidden = !(state.active || state.complete || state.error);
    const percent = Number.isFinite(state.percent) ? Math.max(0, Math.min(100, state.percent)) : 0;
    if (progressBar) {
      progressBar.style.width = percent + "%";
    }
    if (state.active) {
      setState("downloading");
      setSummary(translate("update_available", "Update available"));
      showOnly(null);
      progressLabel.textContent = translate("download_progress", "Downloading") + ": " + Math.round(percent) + "%";
      return;
    }
    if (state.complete) {
      setState("available");
      setSummary(translate("update_available", "Update available"));
      progressLabel.textContent = translate("download_complete", "Download complete.");
      showOnly(launchButton);
      return;
    }
    if (state.error) {
      setState("error");
      setSummary(translate("update_check_failed", "Unable to connect"));
      progressLabel.textContent = translate("download_failed", "Download failed");
      showOnly(checkButton);
    }
  }

  async function refreshUpdateState() {
    const response = await fetch("/update-status", { cache: "no-store" });
    renderUpdateState(await response.json());
  }

  async function pollDownload() {
    try {
      const response = await fetch("/update-download/status", { cache: "no-store" });
      const state = await response.json();
      renderDownloadState(state);
      if (!state.active && progressTimer) {
        window.clearInterval(progressTimer);
        progressTimer = null;
      }
    } catch (_error) {
      renderDownloadState({ error: true, percent: 0 });
      if (progressTimer) {
        window.clearInterval(progressTimer);
        progressTimer = null;
      }
    }
  }

  if (checkButton) {
    checkButton.addEventListener("click", async function () {
      checkButton.disabled = true;
      setState("checking");
      setSummary(translate("update_checking", "Checking..."));
      try {
        const response = await fetch("/check-updates", { method: "POST" });
        renderUpdateState(await response.json());
      } catch (_error) {
        renderUpdateState({ error: true });
      } finally {
        checkButton.disabled = false;
      }
    });
  }

  if (downloadButton) {
    downloadButton.addEventListener("click", async function () {
      downloadButton.disabled = true;
      setState("downloading");
      progress.hidden = false;
      progressLabel.textContent = translate("download_starting", "Starting download...");
      try {
        const response = await fetch("/update-download/start", {
          method: "POST",
          body: tokenBody()
        });
        renderDownloadState(await response.json());
        if (!progressTimer) {
          progressTimer = window.setInterval(pollDownload, 700);
        }
      } catch (_error) {
        renderDownloadState({ error: true, percent: 0 });
      } finally {
        downloadButton.disabled = false;
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

  refreshUpdateState().catch(function () {
    renderUpdateState({ error: true });
  });
});
