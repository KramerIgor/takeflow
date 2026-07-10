// History pagination
window.seedanceHistoryPagerState = window.seedanceHistoryPagerState || {};
    window.seedanceInitHistoryPagination = function () {
      const pageSize = 3;

      for (const container of document.querySelectorAll("[data-history-rail-content]")) {
        const kind = container.dataset.historyRailContent;
        const list = container.querySelector('[data-history-list="' + kind + '"]');
        const pager = container.querySelector('[data-history-pagination="' + kind + '"]');
        if (!kind || !list || !pager) {
          continue;
        }

        const items = Array.from(list.querySelectorAll("[data-history-item]"));
        const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
        const current = Math.min(Math.max(window.seedanceHistoryPagerState[kind] || 1, 1), totalPages);
        window.seedanceHistoryPagerState[kind] = current;

        items.forEach(function (item, index) {
          const visible = index >= (current - 1) * pageSize && index < current * pageSize;
          item.hidden = !visible;
        });

        for (const section of list.querySelectorAll("[data-history-batch-section]")) {
          const visibleItem = Array.from(section.querySelectorAll("[data-history-item]")).some(function (item) {
            return !item.hidden;
          });
          section.hidden = !visibleItem;
        }

        const prev = pager.querySelector("[data-history-page-prev]");
        const next = pager.querySelector("[data-history-page-next]");
        const indicator = pager.querySelector("[data-history-page-indicator]");
        pager.hidden = totalPages <= 1;
        if (indicator) {
          indicator.textContent = current + " / " + totalPages;
        }
        if (prev) {
          prev.disabled = current <= 1;
        }
        if (next) {
          next.disabled = current >= totalPages;
        }
      }
    };

    document.addEventListener("click", function (event) {
      const prev = event.target.closest("[data-history-page-prev]");
      const next = event.target.closest("[data-history-page-next]");
      if (!prev && !next) {
        return;
      }
      const pager = event.target.closest("[data-history-pagination]");
      if (!pager) {
        return;
      }
      const kind = pager.dataset.historyPagination;
      const delta = next ? 1 : -1;
      window.seedanceHistoryPagerState[kind] = (window.seedanceHistoryPagerState[kind] || 1) + delta;
      window.seedanceInitHistoryPagination();
    });

    document.addEventListener("DOMContentLoaded", function () {
      window.seedanceInitHistoryPagination();
    });
