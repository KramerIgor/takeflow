from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
import app.main as main_module
from app.db import list_tasks
from app.main import app


def queued_tasks_count() -> int:
    return len([task for task in list_tasks(limit=1000) if task["status"] == "queued"])


def main() -> int:
    print("=== GUI Start Queue Loop no-task smoke test ===")

    client = TestClient(app)

    index = client.get("/")
    print("index_status_code=", index.status_code, sep="")
    print("contains_queue_loop_button=", "Start Full Queue (paid)" in index.text, sep="")
    print("contains_queue_loop_endpoint=", "/start-queue-loop" in index.text, sep="")
    print("contains_max_tasks_input=", 'name="max_tasks"' in index.text, sep="")

    queued_before = queued_tasks_count()
    print("queued_before=", queued_before, sep="")

    if queued_before != 0:
        print("paid_generation_started=False")
        print("RESULT=SKIPPED_BECAUSE_QUEUED_TASKS_EXIST")
        return 2

    original_process_queue_loop = main_module.process_queue_loop
    original_cleanup = main_module.cleanup_processing_without_request_id
    original_recover = main_module.auto_recover_existing_requests

    calls = []

    def fake_process_queue_loop(**kwargs):
        calls.append(kwargs)
        return {
            "dry_run": False,
            "max_tasks": kwargs.get("max_tasks"),
            "processed_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "stopped_reason": "no_queued_tasks",
            "results": [{"processed": False, "reason": "no_queued_tasks"}],
        }

    main_module.process_queue_loop = fake_process_queue_loop
    main_module.cleanup_processing_without_request_id = lambda: {"new_paid_submit": False}
    main_module.auto_recover_existing_requests = lambda: {"completed_count": 0, "new_paid_submit": False}
    try:
        response = client.post("/start-queue-loop", data={"max_tasks": "2"})
        for _ in range(50):
            if calls:
                break
            import time
            time.sleep(0.05)
    finally:
        main_module.process_queue_loop = original_process_queue_loop
        main_module.cleanup_processing_without_request_id = original_cleanup
        main_module.auto_recover_existing_requests = original_recover

    queued_after = queued_tasks_count()

    print("loop_status_code=", response.status_code, sep="")
    print("contains_background_started_message=", "Queue loop started in background" in response.text, sep="")
    print("background_worker_called=", bool(calls), sep="")
    print("queued_after=", queued_after, sep="")
    print("paid_generation_started=False")

    if (
        index.status_code == 200
        and response.status_code == 200
        and "Start Full Queue (paid)" in index.text
        and "/start-queue-loop" in index.text
        and "Queue loop started in background" in response.text
        and bool(calls)
        and calls[0].get("max_tasks") == 2
        and queued_after == 0
    ):
        print("RESULT=GUI_START_QUEUE_LOOP_NO_TASKS_OK")
        return 0

    print("RESULT=GUI_START_QUEUE_LOOP_NO_TASKS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
