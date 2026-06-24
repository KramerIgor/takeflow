from pathlib import Path
import json
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

import app.main as main
from app.db import delete_task, list_tasks
from app.projects import create_project, get_active_project_name, get_output_root, set_active_project
from app.queue_worker import process_next_queued_task_dry_run
from app.storage import allocate_take_paths


def queued_tasks():
    return [task for task in list_tasks(limit=1000) if task["status"] == "queued"]


def main_test() -> int:
    print("=== Stage 7 flat videos/runs structure check ===")

    output_root = get_output_root()
    previous_active = get_active_project_name()

    project_name = "_stage7_flat_structure_project"
    episode_name = "Episode_99"
    scene_name = "Scene_123"

    project_dir = output_root / project_name
    expected_runs_dir = project_dir / "runs"
    expected_videos_dir = project_dir / "videos"
    expected_stem = f"{episode_name}_{scene_name}_take_000001"
    expected_run_dir = expected_runs_dir / expected_stem
    expected_video_path = expected_videos_dir / f"{expected_stem}.mp4"
    forbidden_nested_dir = project_dir / "results" / episode_name / scene_name

    print("output_root=", output_root, sep="")
    print("previous_active_project=", previous_active, sep="")
    print("project_dir=", project_dir, sep="")
    print("expected_run_dir=", expected_run_dir, sep="")
    print("expected_video_path=", expected_video_path, sep="")

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
                "prompt": "Flat videos runs dry-run structure test. No generation.",
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
        status_path = run_dir / "status.json" if run_dir else None

        status_data = {}
        if status_path and status_path.exists():
            status_data = json.loads(status_path.read_text(encoding="utf-8"))

        print("worker_processed=", worker_result.get("processed"), sep="")
        print("processed_task_status=", processed_task["status"] if processed_task else None, sep="")
        print("run_dir=", run_dir, sep="")
        print("run_dir_is_expected_flat_run_dir=", run_dir == expected_run_dir if run_dir else False, sep="")
        print("runs_dir_exists=", expected_runs_dir.exists(), sep="")
        print("videos_dir_exists=", expected_videos_dir.exists(), sep="")
        print("status_json_exists=", status_path.exists() if status_path else False, sep="")
        print("prompt_exists=", (run_dir / "prompt.txt").exists() if run_dir else False, sep="")
        print("status_expected_video_path=", status_data.get("expected_video_path"), sep="")
        print("expected_video_path_is_flat=", status_data.get("expected_video_path") == str(expected_video_path), sep="")
        print("forbidden_nested_results_dir_exists=", forbidden_nested_dir.exists(), sep="")

        # Direct storage helper check for next take number.
        next_paths = allocate_take_paths(
            project_name=project_name,
            episode_name=episode_name,
            scene_name=scene_name,
        )
        next_run_dir = Path(next_paths["run_dir"])
        print("next_take_stem=", next_paths["take_stem"], sep="")
        print("next_take_is_000002=", next_paths["take_stem"].endswith("_take_000002"), sep="")

        shutil.rmtree(next_run_dir, ignore_errors=True)

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
            and run_dir == expected_run_dir
            and expected_runs_dir.exists()
            and expected_videos_dir.exists()
            and status_path
            and status_path.exists()
            and (run_dir / "prompt.txt").exists()
            and status_data.get("expected_video_path") == str(expected_video_path)
            and not forbidden_nested_dir.exists()
            and next_paths["take_stem"].endswith("_take_000002")
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
        print("RESULT=STAGE7_FLAT_VIDEOS_RUNS_OK")
        return 0

    print("RESULT=STAGE7_FLAT_VIDEOS_RUNS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_test())
