from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "index.html"


def main() -> int:
    html = TEMPLATE_PATH.read_text(encoding="utf-8")

    required = [
        'localStorage.getItem("seedance_gui_active_tab_v1")',
        'new Set(["single-history", "queue-workflow"])',
        "if (!refreshTabs.has(activeTab))",
        "window.location.reload()",
        'window.location.replace("/")',
    ]

    missing = [item for item in required if item not in html]
    if missing:
        print("missing_refresh_guard_parts=" + repr(missing))
        return 1

    print("REFRESH_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
