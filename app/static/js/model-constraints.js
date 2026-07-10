// Model, duration and resolution constraints
window.seedanceModelCapabilities = (window.seedanceConfig && window.seedanceConfig.modelCapabilities) || {};

    function translate(key) {
      return window.seedanceTranslate ? window.seedanceTranslate(key) : key;
    }

    function rateForForm(form) {
      if (!form || !form.elements || !form.elements.model) {
        return null;
      }

      const capabilities = window.seedanceModelCapabilities || {};
      const modelValue = form.elements.model.value || "seedance-2.0";
      const config = capabilities[modelValue] || capabilities["seedance-2.0"];
      if (!config) {
        return null;
      }

      const resolution = form.elements.resolution ? form.elements.resolution.value : "";
      const aspect = form.elements.aspect_ratio ? form.elements.aspect_ratio.value : "16:9";
      const duration = form.elements.duration ? Number.parseFloat(form.elements.duration.value) : NaN;
      if (!Number.isFinite(duration) || duration <= 0) {
        return null;
      }

      if (form.dataset.hasVideoReference === "true") {
        const videoRate = config.video_rates && config.video_rates[resolution];
        return typeof videoRate === "number"
          ? { amount: videoRate * duration, mode: "video" }
          : null;
      }

      const ratesByResolution = (config.text_image_rates && config.text_image_rates[resolution]) || {};
      const textImageRate =
        ratesByResolution[aspect] ||
        ratesByResolution["16:9"] ||
        Object.values(ratesByResolution).find(function (value) {
          return typeof value === "number";
        });
      return typeof textImageRate === "number"
        ? { amount: textImageRate * duration, mode: "text_image" }
        : null;
    }

    function updateCostEstimate(form) {
      if (!form) {
        return;
      }

      const card = form.querySelector("[data-cost-estimate]");
      const valueNode = card ? card.querySelector("[data-cost-estimate-value]") : null;
      const noteNode = card ? card.querySelector("[data-cost-estimate-note]") : null;
      if (!card || !valueNode || !noteNode) {
        return;
      }

      const estimate = rateForForm(form);
      if (!estimate) {
        valueNode.textContent = translate("cost_estimate_unavailable");
        noteNode.textContent = translate("cost_estimate_note");
        return;
      }

      valueNode.textContent = "~$" + estimate.amount.toFixed(4);
      noteNode.textContent = translate(
        estimate.mode === "video" ? "cost_estimate_video" : "cost_estimate_text_image"
      );
    }

    window.seedanceUpdateCostEstimate = updateCostEstimate;

    window.seedanceSyncModelOptions = function (form, desired) {
      if (!form || !form.elements || !form.elements.model) {
        return;
      }

      const capabilities = window.seedanceModelCapabilities || {};
      const modelValue = form.elements.model.value || "seedance-2.0";
      const config = capabilities[modelValue] || capabilities["seedance-2.0"];

      if (!config) {
        return;
      }

      function syncSelect(fieldName, values, defaultValue, labelFn, desiredValue) {
        const field = form.elements[fieldName];
        if (!field || !Array.isArray(values) || !values.length) {
          return;
        }

        const previous = desiredValue ?? field.value;
        field.innerHTML = "";

        for (const value of values) {
          const option = document.createElement("option");
          option.value = String(value);
          option.textContent = labelFn ? labelFn(value) : String(value);
          field.appendChild(option);
        }

        field.value = values.map(String).includes(String(previous)) ? String(previous) : String(defaultValue || values[0]);
      }

      desired = desired || {};
      syncSelect(
        "duration",
        config.durations,
        config.default_duration,
        function (value) { return value + " seconds"; },
        desired.duration
      );
      syncSelect("resolution", config.resolutions, config.default_resolution, null, desired.resolution);
      syncSelect("aspect_ratio", config.aspect_ratios, config.default_aspect_ratio, null, desired.aspect_ratio);
      updateCostEstimate(form);
    };

    document.addEventListener("DOMContentLoaded", function () {
      const forms = Array.from(document.querySelectorAll(".generation-form"));

      for (const form of forms) {
        window.seedanceSyncModelOptions(form);
        updateCostEstimate(form);

        if (form.elements.model) {
          form.elements.model.addEventListener("change", function () {
            window.seedanceSyncModelOptions(form);
            updateCostEstimate(form);
          });
        }

        for (const fieldName of ["duration", "resolution", "aspect_ratio"]) {
          const field = form.elements[fieldName];
          if (field) {
            field.addEventListener("change", function () {
              updateCostEstimate(form);
            });
            field.addEventListener("input", function () {
              updateCostEstimate(form);
            });
          }
        }

        form.addEventListener("seedance:refs-changed", function () {
          updateCostEstimate(form);
        });
        form.addEventListener("seedance:form-prefs-applied", function () {
          updateCostEstimate(form);
        });

        form.addEventListener("submit", function () {
          window.seedanceSyncModelOptions(form);
        });
      }

      document.addEventListener("seedance:language-changed", function () {
        for (const form of forms) {
          updateCostEstimate(form);
        }
      });
    });
