document.addEventListener("DOMContentLoaded", function () {
  const picker = document.querySelector("[data-output-root-picker]");
  const input = document.querySelector("input[name='output_root_path']");
  if (!picker || !input) {
    return;
  }

  const defaultLabel = picker.textContent;

  function translate(key, fallback) {
    if (typeof window.seedanceTranslate === "function") {
      return window.seedanceTranslate(key);
    }
    return fallback;
  }

  picker.addEventListener("click", async function () {
    picker.disabled = true;
    picker.textContent = translate("choosing_output_root", "Choosing...");
    picker.title = "";

    try {
      const response = await fetch("/choose-output-root", {
        method: "POST",
        cache: "no-store"
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Folder picker failed.");
      }
      if (data.path) {
        input.value = data.path;
        input.focus();
      }
    } catch (error) {
      picker.title = error && error.message ? error.message : String(error);
    } finally {
      picker.disabled = false;
      picker.textContent = defaultLabel;
    }
  });
});
