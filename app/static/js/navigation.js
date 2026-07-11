// Sidebar navigation
document.addEventListener("DOMContentLoaded", function () {
      const tabStorageKey = "seedance_gui_active_tab_v1";
      const buttons = Array.from(document.querySelectorAll(".tab-button"));
      const panels = Array.from(document.querySelectorAll(".tab-panel"));

      function activateTab(tabName) {
        if (tabName === "single-history") {
          tabName = "single-generation";
        }

        const targetName = panels.some(function (panel) {
          return panel.dataset.tabPanel === tabName;
        }) ? tabName : "project-settings";

        for (const button of buttons) {
          button.classList.toggle("active", button.dataset.tabTarget === targetName);
        }

        for (const panel of panels) {
          panel.classList.toggle("active", panel.dataset.tabPanel === targetName);
        }

        localStorage.setItem(tabStorageKey, targetName);
        document.dispatchEvent(new CustomEvent("seedance:tab-changed", {
          detail: { tabName: targetName }
        }));
      }

      window.seedanceActivateTab = activateTab;

      for (const button of buttons) {
        button.addEventListener("click", function () {
          activateTab(button.dataset.tabTarget);
        });
      }

      const configuredInitialTab = window.seedanceConfig && window.seedanceConfig.initialTab;
      activateTab(configuredInitialTab || localStorage.getItem(tabStorageKey) || "project-settings");
    });
