from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.db import create_task, delete_task, get_task
from app.main import app
from app.queue_worker import process_next_queued_task_dry_run


def main() -> int:
    print("=== GUI take-folder display check ===")

    params = {
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "gui_take_folder_display_dry_run_no_generation",
    }

    task_id = create_task(
        model="seedance-2.0-fast",
        prompt="GUI take-folder display dry-run test. No generation.",
        params=params,
        refs=[],
        status="queued",
    )

    worker_result = process_next_queued_task_dry_run()
    task = get_task(task_id)
    run_dir = task.get("run_dir") if task else ""

    client = TestClient(app)
    response = client.get("/")

    print("task_id=", task_id, sep="")
    print("worker_processed=", worker_result.get("processed"), sep="")
    print("db_status=", task["status"] if task else None, sep="")
    print("run_dir=", run_dir, sep="")
    print("index_status_code=", response.status_code, sep="")
    print("contains_result_folder_label=", "Result folder:" in response.text, sep="")
    print("contains_take_folder_path=", run_dir in response.text, sep="")
    print("contains_open_result_folder=", "Open result folder" in response.text, sep="")
    print("new_paid_submit_started=False")

    ok = (
        worker_result.get("processed") is True
        and task
        and task["status"] == "completed"
        and "/results/_inbox/take_" in run_dir
        and response.status_code == 200
        and "Result folder:" in response.text
        and run_dir in response.text
        and "Open result folder" in response.text
    )

    delete_task(task_id)
    print("test_db_task_deleted=True")
    print("test_take_folder_left_on_disk=True")

    if ok:
        print("RESULT=GUI_TAKE_FOLDER_DISPLAY_OK")
        return 0

    print("RESULT=GUI_TAKE_FOLDER_DISPLAY_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
