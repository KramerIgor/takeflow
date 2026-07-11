from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys

from frontend_static_utils import read_static_js


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "index.html"
STYLE_PATH = PROJECT_ROOT / "app" / "static" / "style.css"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ.setdefault("SEGMIND_API_KEY", "")
os.environ["TAKEFLOW_DATA_DIR"] = str(PROJECT_ROOT / "tmp_test_output" / "live_history_data")
os.environ["OUTPUT_ROOT"] = str(PROJECT_ROOT / "tmp_test_output" / "live_history_output")

from app.main import generation_progress_for_task


def main() -> int:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    styles = STYLE_PATH.read_text(encoding="utf-8")
    scripts = read_static_js(PROJECT_ROOT)
    started_at = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    processing_task = {
        "status": "processing",
        "model": "seedance-2.0-fast",
        "started_at": started_at,
        "params": {"duration": 15, "resolution": "480p"},
    }
    completed_task = {
        "status": "completed",
        "model": "seedance-2.0-fast",
        "elapsed_total_seconds": 120,
        "params": {"duration": 15, "resolution": "480p"},
    }
    progress = generation_progress_for_task(processing_task, [completed_task, processing_task])

    checks = {
        "processing_progressbar": 'role="progressbar"' in template
        and "estimated_progress_percent" in template,
        "accessible_progress_values": "aria-valuenow" in template
        and "aria-valuemin" in template
        and "aria-valuemax" in template,
        "progress_styles": ".history-generation-progress" in styles
        and ".history-progress-ring" in styles,
        "history_refresh_api": "window.seedanceRefreshHistoryRail" in scripts,
        "single_history_polling": 'window.seedanceRefreshHistoryRail("single"' in scripts,
        "prompt_safe_refresh": "window.location.reload()" not in (
            PROJECT_ROOT / "app" / "static" / "js" / "auto-refresh.js"
        ).read_text(encoding="utf-8"),
        "shutdown_has_terminal_state": "renderShutdownState" in scripts
        and "window.close()" in scripts
        and "response.ok" in scripts,
        "history_average_drives_estimate": bool(
            progress
            and progress["estimated_total_seconds"] == 120
            and progress["estimate_source"] == "history"
            and 40 <= progress["estimated_progress_percent"] <= 60
        ),
    }

    for name, ok in checks.items():
        print(f"{name}={ok}")

    if all(checks.values()):
        print("RESULT=LIVE_HISTORY_UPDATES_OK")
        return 0

    print("RESULT=LIVE_HISTORY_UPDATES_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
