// Shared form state preservation
document.addEventListener("DOMContentLoaded", function () {
      const storageKey = "seedance_gui_form_preferences_v1";
      const forms = Array.from(document.querySelectorAll(".generation-form"));

      if (!forms.length) {
        return;
      }

      const fieldNames = [
        "model",
        "duration",
        "resolution",
        "aspect_ratio",
        "seed",
        "generate_audio",
        "return_last_frame"
      ];

      function loadPrefs() {
        try {
          return JSON.parse(localStorage.getItem(storageKey) || "{}");
        } catch (error) {
          return {};
        }
      }

      function savePrefs() {
        const prefs = {};
        const form = forms.find(function (candidate) {
          return candidate.matches(":focus-within");
        }) || forms[0];

        for (const name of fieldNames) {
          const field = form.elements[name];

          if (!field) {
            continue;
          }

          if (field.type === "checkbox") {
            prefs[name] = field.checked;
          } else {
            prefs[name] = field.value;
          }
        }

        localStorage.setItem(storageKey, JSON.stringify(prefs));
      }

      function applyPrefs() {
        const prefs = loadPrefs();

        for (const form of forms) {
          for (const name of fieldNames) {
            if (!(name in prefs)) {
              continue;
            }

            const field = form.elements[name];

            if (!field) {
              continue;
            }

            if (field.type === "checkbox") {
              field.checked = Boolean(prefs[name]);
            } else {
              field.value = prefs[name];
            }
          }

          if (window.seedanceSyncModelOptions) {
            window.seedanceSyncModelOptions(form, {
              duration: prefs.duration,
              resolution: prefs.resolution,
              aspect_ratio: prefs.aspect_ratio
            });
          }
          if (window.seedanceUpdateCostEstimate) {
            window.seedanceUpdateCostEstimate(form);
          }
          form.dispatchEvent(new CustomEvent("seedance:form-prefs-applied", { bubbles: true }));
        }
      }

      applyPrefs();

      for (const form of forms) {
        for (const name of fieldNames) {
          const field = form.elements[name];

          if (!field) {
            continue;
          }

          field.addEventListener("change", savePrefs);
          field.addEventListener("input", savePrefs);
        }

        form.addEventListener("submit", savePrefs);
      }
    });
