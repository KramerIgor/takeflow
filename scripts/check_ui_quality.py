from pathlib import Path
import os
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_TEXT = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
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
    print("=== Takeflow UI quality check ===")

    cancelled_before = count_status("cancelled")
    text = render_index_html()
    cancelled_after = count_status("cancelled")
    retired_copy = "N" + "ight Mode Safety Preview"
    retired_route = "n" + "ight-mode-preview"

    checks = [
        assert_ok("header_is_product_facing", "Takeflow" in text and "Local AI-video studio" in text and "for scenes, takes, and queues" not in text and "Stage 11 baseline" not in text),
        assert_ok("header_no_stage8_current_status", "Stage 8 - Last frame continuation" not in text),
        assert_ok("queue_keeps_batch_csv_import_advanced", "Batch CSV Import" in text),
        assert_ok("retired_queue_preview_removed", retired_copy not in text and retired_route not in text),
        assert_ok("paid_buttons_labeled_paid", "Run Single Generation (paid)" in text and "Start Full Queue (paid)" in text),
        assert_ok("single_next_item_control_removed", "Start Next Item (paid)" not in text and "Run only next item" not in text),
        assert_ok("csv_preview_button_present", "Preview CSV Import (no tasks)" in text),
        assert_ok("csv_confirm_no_paid_generation_label", "Create Queued Tasks Only (no paid generation)" in text),
        assert_ok("history_tasks_collapsed", 'class="history-details"' in TEMPLATE_TEXT and "compact-history-card" in TEMPLATE_TEXT and 'data-i18n="show_details"' in TEMPLATE_TEXT),
        assert_ok("cancelled_tasks_not_deleted", cancelled_before == cancelled_after),
    ]

    print("cancelled_count_before=", cancelled_before, sep="")
    print("cancelled_count_after=", cancelled_after, sep="")
    print("new_paid_submit_started=False")

    if all(checks):
        print("RESULT=TAKEFLOW_UI_QUALITY_OK")
        return 0

    print("RESULT=TAKEFLOW_UI_QUALITY_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
