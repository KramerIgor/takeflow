document.addEventListener("DOMContentLoaded", function () {
  const mode = document.querySelector("[data-queue-run-mode]");
  const concurrency = document.querySelector("[data-queue-max-concurrency]");
  if (!mode || !concurrency) return;

  function syncConcurrencyState() {
    const parallel = mode.value === "parallel";
    concurrency.disabled = !parallel;
    concurrency.closest("label")?.classList.toggle("control-disabled", !parallel);
  }

  mode.addEventListener("change", syncConcurrencyState);
  syncConcurrencyState();
});
