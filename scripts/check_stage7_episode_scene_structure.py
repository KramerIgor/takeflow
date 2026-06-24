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
    print("=== Stage 7 Episode/Scene structure check ===")

    output_root = get_output_root()
    previous_active = get_active_project_name()

    project_name = "_stage7_episode_scene_project"
    episode_name = "Episode_99"
    scene_name = "Scene_123"

    project_dir = output_root / project_name
    expected_scene_dir = project_dir / "results" / episode_name / scene_name

    print("output_root=", output_root, sep="")
    print("previous_active_project=", previous_active, sep="")
    print("project_dir=", project_dir, sep="")
    print("expected_scene_dir=", expected_scene_dir, sep="")

    shutil.rmtree(project_dir, ignore_errors=True)

    existing_queued = queued_tasks()
    print("existing_queued_before=", len(existing_queued), sep="")

    if existing_queued:
        print("new_paid_submit_started=False")
        print("RESULT=SKIPPED_EXISTING_QUEUED_TASKS")
        return 2

    task_id = None

    try:
        create_project(project_name)
        set_active_project(project_name)

        client = TestClient(main.app)

        index_before = client.get("/")
        add_response = client.post(
            "/add-to-queue",
            data={
                "prompt": "Episode Scene dry-run structure test. No generation.",
                "model": "seedance-2.0-fast",
                "duration": "4",
                "resolution": "480p",
                "aspect_ratio": "16:9",
                "episode_name": episode_name,
                "scene_name": scene_name,
                "seed": "-1",
            },
        )

        queued_after_add = queued_tasks()
        task = queued_after_add[0] if queued_after_add else None
        task_id = task["id"] if task else None

        print("index_before_status_code=", index_before.status_code, sep="")
        print("add_response_status_code=", add_response.status_code, sep="")
        print("contains_episode_field=", 'name="episode_name"' in index_before.text, sep="")
        print("contains_scene_field=", 'name="scene_name"' in index_before.text, sep="")
        print("queued_after_add=", len(queued_after_add), sep="")
        print("task_id=", task_id, sep="")
        print("task_project_name=", task["params"].get("project_name") if task else None, sep="")
        print("task_episode_name=", task["params"].get("episode_name") if task else None, sep="")
        print("task_scene_name=", task["params"].get("scene_name") if task else None, sep="")

        worker_result = process_next_queued_task_dry_run()

        processed_task = None
        for item in list_tasks(limit=1000):
            if item["id"] == task_id:
                processed_task = item
                break

        run_dir = Path(processed_task["run_dir"]) if processed_task and processed_task.get("run_dir") else None

        print("worker_processed=", worker_result.get("processed"), sep="")
        print("processed_task_status=", processed_task["status"] if processed_task else None, sep="")
        print("run_dir=", run_dir, sep="")
        print("run_dir_inside_expected_scene=", str(run_dir).startswith(str(expected_scene_dir)) if run_dir else False, sep="")
        print("expected_scene_dir_exists=", expected_scene_dir.exists(), sep="")
        print("status_json_exists=", (run_dir / "status.json").exists() if run_dir else False, sep="")
        print("prompt_exists=", (run_dir / "prompt.txt").exists() if run_dir else False, sep="")
        print("new_paid_submit_started=False")

        ok = (
            index_before.status_code == 200
            and add_response.status_code == 200
            and 'name="episode_name"' in index_before.text
            and 'name="scene_name"' in index_before.text
            and task
            and task["params"].get("project_name") == project_name
            and task["params"].get("episode_name") == episode_name
            and task["params"].get("scene_name") == scene_name
            and worker_result.get("processed") is True
            and processed_task
            and processed_task["status"] == "completed"
            and run_dir
            and str(run_dir).startswith(str(expected_scene_dir))
            and expected_scene_dir.exists()
            and (run_dir / "status.json").exists()
            and (run_dir / "prompt.txt").exists()
        )

    finally:
        if task_id is not None:
            delete_task(task_id)

        set_active_project(previous_active)
        shutil.rmtree(project_dir, ignore_errors=True)

    print("restored_active_project=", get_active_project_name(), sep="")
    print("test_project_deleted=True")
    print("test_db_task_deleted=True")

    if ok and get_active_project_name() == previous_active:
        print("RESULT=STAGE7_EPISODE_SCENE_STRUCTURE_OK")
        return 0

    print("RESULT=STAGE7_EPISODE_SCENE_STRUCTURE_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_test())
