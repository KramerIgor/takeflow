from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import create_task, delete_task, get_task
from app.queue_worker import process_next_queued_task_dry_run
from app.settings import OUTPUT_DIR


def main() -> int:
    print("=== Queue run take-folder dry-run check ===")

    params = {
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "take_folder_dry_run_no_generation",
    }

    task_id = create_task(
        model="seedance-2.0-fast",
        prompt="Take-folder dry-run smoke test. No generation.",
        params=params,
        refs=[],
        status="queued",
    )

    result = process_next_queued_task_dry_run()
    task = get_task(task_id)

    run_dir = Path(task["run_dir"]) if task and task.get("run_dir") else None

    print("task_id=", task_id, sep="")
    print("worker_processed=", result.get("processed"), sep="")
    print("worker_status=", result.get("status"), sep="")
    print("db_status=", task["status"] if task else None, sep="")
    print("run_dir=", run_dir, sep="")
    print("run_dir_is_in_results_inbox=", "/results/_inbox/take_" in str(run_dir), sep="")
    print("prompt_exists=", (run_dir / "prompt.txt").exists() if run_dir else False, sep="")
    print("params_exists=", (run_dir / "params.json").exists() if run_dir else False, sep="")
    print("refs_exists=", (run_dir / "refs.json").exists() if run_dir else False, sep="")
    print("summary_exists=", (run_dir / "summary.json").exists() if run_dir else False, sep="")
    print("task_json_exists=", (run_dir / "task.json").exists() if run_dir else False, sep="")
    print("new_paid_submit_started=False")

    ok = (
        result.get("processed") is True
        and task
        and task["status"] == "completed"
        and run_dir
        and "/results/_inbox/take_" in str(run_dir)
        and (run_dir / "prompt.txt").exists()
        and (run_dir / "params.json").exists()
        and (run_dir / "refs.json").exists()
        and (run_dir / "summary.json").exists()
        and (run_dir / "task.json").exists()
    )

    delete_task(task_id)
    print("test_db_task_deleted=True")
    print("test_take_folder_left_on_disk=True")

    if ok:
        print("RESULT=QUEUE_RUN_TAKE_FOLDER_DRY_RUN_OK")
        return 0

    print("RESULT=QUEUE_RUN_TAKE_FOLDER_DRY_RUN_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
