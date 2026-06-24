from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import create_task, delete_task, get_task
from app.queue_worker import process_next_queued_task_dry_run


def main() -> int:
    print("=== status.json take-folder check ===")

    params = {
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "status_json_take_folder_dry_run_no_generation",
    }

    task_id = create_task(
        model="seedance-2.0-fast",
        prompt="status.json dry-run smoke test. No generation.",
        params=params,
        refs=[],
        status="queued",
    )

    result = process_next_queued_task_dry_run()
    task = get_task(task_id)

    run_dir = Path(task["run_dir"]) if task and task.get("run_dir") else None
    status_path = run_dir / "status.json" if run_dir else None

    print("task_id=", task_id, sep="")
    print("worker_processed=", result.get("processed"), sep="")
    print("db_status=", task["status"] if task else None, sep="")
    print("run_dir=", run_dir, sep="")
    print("status_json_exists=", status_path.exists() if status_path else False, sep="")

    status_data = {}
    if status_path and status_path.exists():
        status_data = json.loads(status_path.read_text(encoding="utf-8"))

    print("status_json_status=", status_data.get("status"), sep="")
    print("status_json_task_id=", status_data.get("task_id"), sep="")
    print("new_paid_submit_started=False")

    ok = (
        result.get("processed") is True
        and task
        and task["status"] == "completed"
        and status_path
        and status_path.exists()
        and status_data.get("status") == "completed"
        and status_data.get("task_id") == task_id
    )

    delete_task(task_id)
    print("test_db_task_deleted=True")
    print("test_take_folder_left_on_disk=True")

    if ok:
        print("RESULT=STATUS_JSON_TAKE_FOLDER_OK")
        return 0

    print("RESULT=STATUS_JSON_TAKE_FOLDER_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
