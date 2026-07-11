function normalizeSeed(value) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function syncSeedControl(form) {
  const input = form && form.querySelector("[data-fixed-seed-input]");
  const randomToggle = form && form.querySelector("[data-random-seed]");
  if (!input || !randomToggle) {
    return;
  }

  if (randomToggle.checked) {
    const current = normalizeSeed(input.value);
    if (current !== null) {
      input.dataset.fixedSeed = String(current);
    }
    input.value = "-1";
    input.hidden = true;
    return;
  }

  const restored = normalizeSeed(input.dataset.fixedSeed) ?? normalizeSeed(input.value) ?? 42;
  input.value = String(restored);
  input.dataset.fixedSeed = String(restored);
  input.hidden = false;
}

function applySeedState(form, item) {
  const input = form && form.querySelector("[data-fixed-seed-input]");
  const randomToggle = form && form.querySelector("[data-random-seed]");
  if (!input || !randomToggle) {
    return;
  }

  const requested = normalizeSeed(item && item.requested_seed);
  const actual = normalizeSeed(item && item.actual_seed);
  const legacy = normalizeSeed(item && item.seed);
  const isRandom = item && typeof item.random_seed === "boolean"
    ? item.random_seed
    : requested === null && legacy === null;

  input.dataset.fixedSeed = String(actual ?? requested ?? legacy ?? 42);
  randomToggle.checked = Boolean(isRandom);
  input.value = randomToggle.checked ? "-1" : input.dataset.fixedSeed;
  syncSeedControl(form);
}

window.seedanceApplySeedState = applySeedState;
window.seedanceSyncSeedControl = syncSeedControl;

document.addEventListener("DOMContentLoaded", function () {
  for (const form of document.querySelectorAll(".generation-form")) {
    const input = form.querySelector("[data-fixed-seed-input]");
    const randomToggle = form.querySelector("[data-random-seed]");
    if (!input || !randomToggle) {
      continue;
    }

    randomToggle.addEventListener("change", function () {
      syncSeedControl(form);
    });
    input.addEventListener("input", function () {
      const fixed = normalizeSeed(input.value);
      if (fixed !== null) {
        input.dataset.fixedSeed = String(fixed);
      }
    });
    form.addEventListener("seedance:form-prefs-applied", function () {
      syncSeedControl(form);
    });
    form.addEventListener("submit", function () {
      syncSeedControl(form);
    });
    syncSeedControl(form);
  }
});
