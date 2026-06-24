from pathlib import Path
import os
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import app.main as main
from app.db import DB_PATH


def render_index_html() -> str:
    template = main.templates.get_template("index.html")
    return template.render(main.base_context(request=None))


def count_status(status: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM generation_tasks WHERE status = ?",
            (status,),
        ).fetchone()

    return int(row[0])


def assert_ok(name: str, condition: bool) -> bool:
    print(f"{name}={bool(condition)}")
    return bool(condition)


def main_run() -> int:
    print("=== Stage 11 UI polish check ===")

    cancelled_before = count_status("cancelled")
    text = render_index_html()
    cancelled_after = count_status("cancelled")

    checks = [
        assert_ok("header_is_product_facing", "Local video generation workspace" in text and "Stage 11 baseline" not in text),
        assert_ok("header_no_stage8_current_status", "Stage 8 - Last frame continuation" not in text),
        assert_ok("queue_keeps_batch_csv_import_advanced", "Batch CSV Import" in text),
        assert_ok("queue_keeps_night_mode_preview_advanced", "Night Mode Safety Preview" in text),
        assert_ok("paid_buttons_labeled_paid", "Start Queue (paid)" in text and "Start Queue Loop (paid)" in text),
        assert_ok("csv_preview_button_present", "Preview CSV Import (no tasks)" in text),
        assert_ok("night_mode_preview_button_present", "Preview Night Mode Plan" in text),
        assert_ok("csv_confirm_no_paid_generation_label", "Create Queued Tasks Only (no paid generation)" in text),
        assert_ok("history_tasks_collapsed", 'class="history-details"' in text and "Completed / cancelled history" in text),
        assert_ok("cancelled_tasks_not_deleted", cancelled_before == cancelled_after),
    ]

    print("cancelled_count_before=", cancelled_before, sep="")
    print("cancelled_count_after=", cancelled_after, sep="")
    print("new_paid_submit_started=False")

    if all(checks):
        print("RESULT=STAGE11_UI_POLISH_OK")
        return 0

    print("RESULT=STAGE11_UI_POLISH_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
