document.addEventListener("DOMContentLoaded", function () {
  const button = document.querySelector("[data-shutdown-server]");
  if (!button) {
    return;
  }

  function translate(key, fallback) {
    return typeof window.seedanceTranslate === "function" ? window.seedanceTranslate(key) : fallback;
  }

  async function confirmShutdown() {
    if (typeof window.seedanceConfirmAction === "function") {
      return window.seedanceConfirmAction("confirm_shutdown_server");
    }
    return window.confirm(translate("confirm_shutdown_server", "Shut down Takeflow server?"));
  }

  function renderShutdownState() {
    const main = document.querySelector("main");
    if (!main) {
      return;
    }

    main.className = "shutdown-screen";
    main.replaceChildren();

    const panel = document.createElement("section");
    panel.className = "shutdown-screen-panel";

    const title = document.createElement("h1");
    title.textContent = translate("shutdown_complete", "Takeflow is off");

    const message = document.createElement("p");
    message.textContent = translate("shutdown_safe_to_close", "You can close this tab.");

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "secondary-button";
    closeButton.textContent = translate("close_tab", "Close tab");
    closeButton.addEventListener("click", function () {
      window.close();
    });

    panel.append(title, message, closeButton);
    main.append(panel);

    window.setTimeout(function () {
      window.close();
    }, 150);
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
      const response = await fetch("/shutdown", {
        method: "POST",
        body
      });
      if (!response.ok) {
        throw new Error("Shutdown failed with HTTP " + response.status);
      }
      renderShutdownState();
    } catch (error) {
      button.disabled = false;
      button.textContent = translate("shutdown_failed", "Takeflow could not be shut down");
      window.setTimeout(function () {
        button.textContent = translate("shutdown_server", "Quit");
      }, 1800);
    }
  });
});
