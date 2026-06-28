from pathlib import Path
import sys
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.db import create_task, delete_task
from app.main import app, queue_tasks_for_view
from app.projects import get_active_project_dir, get_active_project_name


def expect(name, condition):
    print(f"{name}={condition}")
    return bool(condition)


def main():
    print("=== Queue history cards check ===")

    marker = uuid.uuid4().hex[:8]
    prompt = f"QUEUE_HISTORY_CARD_CHECK_{marker}"
    task_id = create_task(
        model="seedance-2.0-fast",
        prompt=prompt,
        params={
            "project_name": get_active_project_name(),
            "project_dir": str(get_active_project_dir()),
            "episode_name": "Episode_01",
            "scene_name": "Scene_001",
            "model": "seedance-2.0-fast",
            "prompt": prompt,
            "reference_images": [],
            "reference_videos": [],
            "reference_audios": [],
            "duration": 4,
            "resolution": "480p",
            "aspect_ratio": "16:9",
            "generate_audio": False,
            "seed": -1,
            "return_last_frame": True,
            "skip_moderation": False,
            "mode": "queue_history_card_check_no_generation",
        },
        refs=[],
        status="queued",
    )

    try:
        tasks, batches, summary = queue_tasks_for_view()
        html = TestClient(app).get("/").text

        checks = [
            expect("batches_available", isinstance(batches, list)),
            expect("queue_overall_summary_visible", "Queue progress" in html and "Estimated total cost" in html),
            expect("queue_batch_progress_visible", "queue-batch-progress" in html),
            expect("queue_total_estimated_cost_visible", "~$" in html and "estimated" in html),
            expect("queue_labels_present", bool(batches) and all("queue_label" in batch for batch in batches)),
            expect("item_labels_present", bool(tasks) and all("queue_item_label" in task for task in tasks)),
            expect("history_card_macro_rendered", "queue-history-card" in html),
            expect("queue_batch_title_rendered", "queue-batch-title" in html),
            expect("queue_history_json_present", html.count("history-item-data") >= 1),
            expect("balance_in_topbar", "top-balance" in html and "Balance" in html),
            expect("technical_id_debug_only", "Technical task ID" in html),
            expect("queue_edit_button", "queue-edit-button" in html),
            expect("remove_queue_route", "/remove-queued-task/" in html),
            expect("update_queue_route_js", "/update-queued-task/" in html),
            expect("temporary_prompt_visible", prompt in html),
        ]
    finally:
        delete_task(task_id)

    print("test_task_deleted=True")
    print("new_paid_submit_started=False")

    if all(checks):
        print("RESULT=QUEUE_HISTORY_CARDS_OK")
        return 0
    print("RESULT=QUEUE_HISTORY_CARDS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
