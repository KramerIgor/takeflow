document.addEventListener("DOMContentLoaded", function () {
  const button = document.querySelector("[data-shutdown-server]");
  if (!button) {
    return;
  }

  function translate(key, fallback) {
    if (typeof window.seedanceTranslate === "function") {
      return window.seedanceTranslate(key);
    }
    return fallback;
  }

  async function confirmShutdown() {
    if (typeof window.seedanceConfirmAction === "function") {
      return window.seedanceConfirmAction("confirm_shutdown_server");
    }
    return window.confirm(translate("confirm_shutdown_server", "Shut down Takeflow server?"));
  }

  button.addEventListener("click", async function () {
    const ok = await confirmShutdown();
    if (!ok) {
      return;
    }

    button.disabled = true;
    button.textContent = translate("shutting_down", "Shutting down...");

    const body = new URLSearchParams();
    body.set("token", (window.seedanceConfig && window.seedanceConfig.shutdownToken) || "");

    try {
      await fetch("/shutdown", {
        method: "POST",
        body
      });
    } catch (error) {
      // The server may close the connection before the browser receives the response.
    }
  });
});
