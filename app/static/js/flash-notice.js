document.addEventListener("DOMContentLoaded", function () {
  const notice = document.querySelector("[data-flash-notice]");
  if (!notice) {
    return;
  }

  let dismissed = false;
  function dismiss() {
    if (dismissed) {
      return;
    }
    dismissed = true;
    notice.classList.add("is-dismissing");
    window.setTimeout(function () {
      notice.remove();
    }, 180);
  }

  notice.querySelector("[data-flash-dismiss]")?.addEventListener("click", dismiss);
  document.addEventListener("seedance:tab-changed", dismiss, { once: true });
  window.setTimeout(dismiss, 6000);
});
