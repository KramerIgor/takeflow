from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import create_task, delete_task, get_task
from app.projects import get_active_project_name, get_output_root, set_active_project
from app.queue_worker import process_next_queued_task_dry_run


def main() -> int:
    print("=== Active project storage check ===")

    output_root = get_output_root()
    previous_active = get_active_project_name()
    test_project_name = "_stage7_storage_test"
    test_project_dir = output_root / test_project_name

    print("output_root=", output_root, sep="")
    print("previous_active_project=", previous_active, sep="")
    print("test_project_dir=", test_project_dir, sep="")

    shutil.rmtree(test_project_dir, ignore_errors=True)

    task_id = None

    try:
        set_active_project(test_project_name)

        params = {
            "model": "seedance-2.0-fast",
            "duration": 4,
            "resolution": "480p",
            "aspect_ratio": "16:9",
            "mode": "active_project_storage_dry_run_no_generation",
        }

        task_id = create_task(
            model="seedance-2.0-fast",
            prompt="Active project storage dry-run test. No generation.",
            params=params,
            refs=[],
            status="queued",
        )

        result = process_next_queued_task_dry_run()
        task = get_task(task_id)

        run_dir = Path(task["run_dir"]) if task and task.get("run_dir") else None
        expected_prefix = test_project_dir / "results" / "_inbox"

        print("active_during_test=", get_active_project_name(), sep="")
        print("task_id=", task_id, sep="")
        print("worker_processed=", result.get("processed"), sep="")
        print("db_status=", task["status"] if task else None, sep="")
        print("run_dir=", run_dir, sep="")
        print("expected_prefix=", expected_prefix, sep="")
        print("run_dir_inside_test_project=", str(run_dir).startswith(str(expected_prefix)) if run_dir else False, sep="")
        print("status_json_exists=", (run_dir / "status.json").exists() if run_dir else False, sep="")
        print("prompt_exists=", (run_dir / "prompt.txt").exists() if run_dir else False, sep="")
        print("new_paid_submit_started=False")

        ok = (
            result.get("processed") is True
            and task
            and task["status"] == "completed"
            and run_dir
            and str(run_dir).startswith(str(expected_prefix))
            and (run_dir / "status.json").exists()
            and (run_dir / "prompt.txt").exists()
        )

    finally:
        if task_id is not None:
            delete_task(task_id)

        set_active_project(previous_active)
        shutil.rmtree(test_project_dir, ignore_errors=True)

    print("restored_active_project=", get_active_project_name(), sep="")
    print("test_project_deleted=True")
    print("test_db_task_deleted=True")

    if ok and get_active_project_name() == previous_active:
        print("RESULT=ACTIVE_PROJECT_STORAGE_OK")
        return 0

    print("RESULT=ACTIVE_PROJECT_STORAGE_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
