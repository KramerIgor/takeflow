from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.main import app, queue_tasks_for_view


def expect(name, condition):
    print(f"{name}={condition}")
    return bool(condition)


def main():
    print("=== Queue history cards check ===")
    tasks, batches = queue_tasks_for_view()
    html = TestClient(app).get("/").text

    checks = [
        expect("batches_available", isinstance(batches, list)),
        expect("queue_labels_present", (not batches) or all("queue_label" in batch for batch in batches)),
        expect("item_labels_present", (not tasks) or all("queue_item_label" in task for task in tasks)),
        expect("history_card_macro_rendered", "queue-history-card" in html),
        expect("queue_batch_title_rendered", "queue-batch-title" in html),
        expect("queue_history_json_present", html.count("history-item-data") >= len(tasks[:1])),
        expect("balance_in_topbar", "top-balance" in html and "Balance" in html),
        expect("technical_id_debug_only", "Technical task ID" in html),
        expect("queue_edit_button", "queue-edit-button" in html),
        expect("remove_queue_route", "/remove-queued-task/" in html),
        expect("update_queue_route_js", "/update-queued-task/" in html),
    ]

    if all(checks):
        print("RESULT=QUEUE_HISTORY_CARDS_OK")
        return 0
    print("RESULT=QUEUE_HISTORY_CARDS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
