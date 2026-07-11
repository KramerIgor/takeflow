from __future__ import annotations

from pathlib import Path

from frontend_static_utils import read_static_js


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "index.html"


def main() -> int:
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    app_js = read_static_js(PROJECT_ROOT)
    combined = html + "\n" + app_js

    required = [
        'window.seedanceRefreshProcessingHistoryCards("single")',
        'window.seedanceRefreshProcessingHistoryCards("queue")',
        "autoRefreshEnabled",
        "refreshIntervalMs",
        '<script type="module" src="/static/app.js?v={{ static_asset_version }}"></script>',
        'event.target.closest("[data-refresh-history]")',
        'refreshButton.dataset.refreshHistory || "single"',
        'const selector = \'[data-history-rail-content="\' + historyKind + \'"]\'',
        "document.querySelector(selector)",
        'railContent.closest(".history-rail-panel")',
        "freshContent = doc.querySelector(selector)",
        'freshContent.closest(".history-rail-panel")',
        "window.seedanceInitHistoryPagination()",
        "card.replaceWith(replacement)",
        "window.seedanceLocalizeRoot(replacement, lang)",
    ]

    missing = [item for item in required if item not in combined]
    if missing:
        print("missing_refresh_guard_parts=" + repr(missing))
        return 1

    forbidden = ["window.location.reload()", 'window.location.replace("/")']
    present_forbidden = [item for item in forbidden if item in combined]
    if present_forbidden:
        print("forbidden_refresh_guard_parts=" + repr(present_forbidden))
        return 1

    auto_refresh = (PROJECT_ROOT / "app" / "static" / "js" / "auto-refresh.js").read_text(encoding="utf-8")
    if "seedanceRefreshHistoryRail" in auto_refresh or "railPanel.innerHTML" in auto_refresh:
        print("automatic_refresh_is_not_targeted=True")
        return 1

    print("REFRESH_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
