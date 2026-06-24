from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

import app.main as main
from app.db import delete_task, list_tasks
from app.projects import create_project, get_active_project_name, get_output_root, set_active_project
from app.queue_worker import process_next_queued_task_dry_run


def queued_tasks():
    return [task for task in list_tasks(limit=1000) if task["status"] == "queued"]


def main_test() -> int:
    print("=== Queued task project binding check ===")

    output_root = get_output_root()
    previous_active = get_active_project_name()

    project_a = "_stage7_bind_project_a"
    project_b = "_stage7_bind_project_b"

    project_a_dir = output_root / project_a
    project_b_dir = output_root / project_b

    print("output_root=", output_root, sep="")
    print("previous_active_project=", previous_active, sep="")

    shutil.rmtree(project_a_dir, ignore_errors=True)
    shutil.rmtree(project_b_dir, ignore_errors=True)

    existing_queued = queued_tasks()
    print("existing_queued_before=", len(existing_queued), sep="")

    if existing_queued:
        print("RESULT=SKIPPED_EXISTING_QUEUED_TASKS")
        return 2

    task_id = None

    try:
        create_project(project_a)
        create_project(project_b)

        set_active_project(project_a)

        client = TestClient(main.app)

        add_response = client.post(
            "/add-to-queue",
            data={
                "prompt": "Project binding dry-run test. No generation.",
                "model": "seedance-2.0-fast",
                "duration": "4",
                "resolution": "480p",
                "aspect_ratio": "16:9",
                "seed": "-1",
            },
        )

        queued_after_add = queued_tasks()
        task = queued_after_add[0] if queued_after_add else None
        task_id = task["id"] if task else None

        print("add_response_status_code=", add_response.status_code, sep="")
        print("queued_after_add=", len(queued_after_add), sep="")
        print("task_id=", task_id, sep="")
        print("task_project_name=", task["params"].get("project_name") if task else None, sep="")
        print("task_project_dir=", task["params"].get("project_dir") if task else None, sep="")

        set_active_project(project_b)
        print("active_project_before_worker=", get_active_project_name(), sep="")

        worker_result = process_next_queued_task_dry_run()

        processed_task = None
        for item in list_tasks(limit=1000):
            if item["id"] == task_id:
                processed_task = item
                break

        run_dir = Path(processed_task["run_dir"]) if processed_task and processed_task.get("run_dir") else None
        expected_prefix = project_a_dir / "results" / "_inbox"
        wrong_prefix = project_b_dir / "results" / "_inbox"

        print("worker_processed=", worker_result.get("processed"), sep="")
        print("processed_task_status=", processed_task["status"] if processed_task else None, sep="")
        print("run_dir=", run_dir, sep="")
        print("expected_project_a_prefix=", expected_prefix, sep="")
        print("wrong_project_b_prefix=", wrong_prefix, sep="")
        print("run_dir_inside_original_project_a=", str(run_dir).startswith(str(expected_prefix)) if run_dir else False, sep="")
        print("run_dir_inside_current_project_b=", str(run_dir).startswith(str(wrong_prefix)) if run_dir else False, sep="")
        print("status_json_exists=", (run_dir / "status.json").exists() if run_dir else False, sep="")
        print("new_paid_submit_started=False")

        ok = (
            add_response.status_code == 200
            and task
            and task["params"].get("project_name") == project_a
            and worker_result.get("processed") is True
            and processed_task
            and processed_task["status"] == "completed"
            and run_dir
            and str(run_dir).startswith(str(expected_prefix))
            and not str(run_dir).startswith(str(wrong_prefix))
            and (run_dir / "status.json").exists()
        )

    finally:
        if task_id is not None:
            delete_task(task_id)

        set_active_project(previous_active)
        shutil.rmtree(project_a_dir, ignore_errors=True)
        shutil.rmtree(project_b_dir, ignore_errors=True)

    print("restored_active_project=", get_active_project_name(), sep="")
    print("test_projects_deleted=True")
    print("test_db_task_deleted=True")

    if ok and get_active_project_name() == previous_active:
        print("RESULT=QUEUED_TASK_PROJECT_BINDING_OK")
        return 0

    print("RESULT=QUEUED_TASK_PROJECT_BINDING_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_test())
