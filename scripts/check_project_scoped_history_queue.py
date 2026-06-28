from pathlib import Path
import shutil
import sys
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

import app.main as main
from app.db import create_task, delete_task, get_next_queued_task, get_task
from app.projects import create_project, get_active_project_name, get_output_root, set_active_project
from app.queue_worker import process_queue_loop


def expect(name, condition):
    print(f"{name}={condition}")
    return bool(condition)


def make_params(project_name, project_dir, prompt, mode):
    return {
        "project_name": project_name,
        "project_dir": str(project_dir),
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
        "mode": mode,
    }


def make_task(project_name, project_dir, prompt, mode, status):
    return create_task(
        model="seedance-2.0-fast",
        prompt=prompt,
        params=make_params(project_name, project_dir, prompt, mode),
        refs=[],
        status=status,
    )


def main_test() -> int:
    print("=== Project-scoped History and Queue check ===")

    output_root = get_output_root()
    previous_active = get_active_project_name()
    suffix = uuid.uuid4().hex[:8]
    project_a = f"_scope_project_a_{suffix}"
    project_b = f"_scope_project_b_{suffix}"
    project_a_dir = output_root / project_a
    project_b_dir = output_root / project_b
    created_task_ids = []

    a_history_prompt = f"PROJECT_SCOPE_A_HISTORY_{suffix}"
    b_history_prompt = f"PROJECT_SCOPE_B_HISTORY_{suffix}"
    a_queue_prompt = f"PROJECT_SCOPE_A_QUEUE_{suffix}"
    b_queue_prompt = f"PROJECT_SCOPE_B_QUEUE_{suffix}"

    try:
        create_project(project_a)
        create_project(project_b)

        a_history_id = make_task(project_a, project_a_dir, a_history_prompt, "single_generation_paid", "completed")
        b_history_id = make_task(project_b, project_b_dir, b_history_prompt, "single_generation_paid", "completed")
        a_queue_id = make_task(project_a, project_a_dir, a_queue_prompt, "queued_no_generation_yet", "queued")
        b_queue_id = make_task(project_b, project_b_dir, b_queue_prompt, "queued_no_generation_yet", "queued")
        created_task_ids.extend([a_history_id, b_history_id, a_queue_id, b_queue_id])

        client = TestClient(main.app)

        set_active_project(project_a)
        history_a = main.single_generation_history_for_view(limit=20)
        queue_a, _ = main.queue_tasks_for_view()
        next_a = get_next_queued_task(**main.active_project_task_filter())
        html_a = client.get("/").text

        set_active_project(project_b)
        history_b = main.single_generation_history_for_view(limit=20)
        queue_b, _ = main.queue_tasks_for_view()
        next_b = get_next_queued_task(**main.active_project_task_filter())
        html_b = client.get("/").text

        loop_b = process_queue_loop(
            dry_run=True,
            max_tasks=1,
            stop_on_failure=True,
            **main.active_project_task_filter(),
        )
        a_queue_after_loop = get_task(a_queue_id)
        b_queue_after_loop = get_task(b_queue_id)

        checks = [
            expect("history_a_contains_only_project_a_prompt", any(item.get("prompt") == a_history_prompt for item in history_a) and all(item.get("prompt") != b_history_prompt for item in history_a)),
            expect("queue_a_contains_only_project_a_prompt", any(item.get("prompt") == a_queue_prompt for item in queue_a) and all(item.get("prompt") != b_queue_prompt for item in queue_a)),
            expect("html_a_excludes_project_b_prompts", b_history_prompt not in html_a and b_queue_prompt not in html_a),
            expect("history_b_contains_only_project_b_prompt", any(item.get("prompt") == b_history_prompt for item in history_b) and all(item.get("prompt") != a_history_prompt for item in history_b)),
            expect("queue_b_contains_only_project_b_prompt", any(item.get("prompt") == b_queue_prompt for item in queue_b) and all(item.get("prompt") != a_queue_prompt for item in queue_b)),
            expect("html_b_excludes_project_a_prompts", a_history_prompt not in html_b and a_queue_prompt not in html_b),
            expect("next_queued_task_respects_project_a", next_a and int(next_a["id"]) == a_queue_id),
            expect("next_queued_task_respects_project_b", next_b and int(next_b["id"]) == b_queue_id),
            expect("queue_loop_processes_only_active_project_b", loop_b.get("processed_count") == 1 and loop_b.get("results", [{}])[0].get("task_id") == b_queue_id),
            expect("project_a_queue_left_queued", a_queue_after_loop and a_queue_after_loop.get("status") == "queued"),
            expect("project_b_queue_processed", b_queue_after_loop and b_queue_after_loop.get("status") == "completed"),
        ]

    finally:
        for task_id in created_task_ids:
            delete_task(task_id)
        set_active_project(previous_active)
        shutil.rmtree(project_a_dir, ignore_errors=True)
        shutil.rmtree(project_b_dir, ignore_errors=True)

    print("restored_active_project=", get_active_project_name(), sep="")
    print("test_tasks_deleted=True")
    print("test_projects_deleted=True")
    print("new_paid_submit_started=False")

    if all(checks) and get_active_project_name() == previous_active:
        print("RESULT=PROJECT_SCOPED_HISTORY_QUEUE_OK")
        return 0

    print("RESULT=PROJECT_SCOPED_HISTORY_QUEUE_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_test())
