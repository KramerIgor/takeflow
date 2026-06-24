from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

import app.main as main
from app.db import list_tasks


def find_completed_task_with_last_frame():
    for task in list_tasks(limit=1000):
        if task.get("status") != "completed":
            continue

        output_path = task.get("output_path")
        run_dir = task.get("run_dir")

        candidates = []

        if run_dir:
            candidates.append(Path(run_dir) / "last_frame.png")

        if output_path:
            output = Path(output_path)
            if output.parent.name == "videos":
                candidates.append(output.parent.parent / "runs" / output.stem / "last_frame.png")

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return task, candidate

    return None, None


def get_new_task(before_ids):
    new_tasks = [task for task in list_tasks(limit=1000) if int(task["id"]) not in before_ids]

    if not new_tasks:
        return None

    return sorted(new_tasks, key=lambda task: int(task["id"]), reverse=True)[0]


def main_run():
    print("=== Stage 8 Continue from previous take GUI check ===")

    parent_task, last_frame = find_completed_task_with_last_frame()

    print("parent_task_found=", parent_task is not None, sep="")

    if not parent_task:
        print("new_paid_submit_started=False")
        print("RESULT=STAGE8_CONTINUE_BUTTON_FAILED_NO_PARENT")
        return 1

    parent_task_id = int(parent_task["id"])
    print("parent_task_id=", parent_task_id, sep="")
    print("parent_last_frame_path=", last_frame, sep="")
    print("parent_last_frame_exists=", last_frame.exists(), sep="")

    client = TestClient(main.app)

    index_response = client.get("/")
    print("index_status_code=", index_response.status_code, sep="")
    print("index_contains_continue_button=", "Continue from previous take" in index_response.text, sep="")
    print("index_contains_continue_route=", f"/continue-from-task/{parent_task_id}" in index_response.text, sep="")

    before_ids = {int(task["id"]) for task in list_tasks(limit=1000)}

    response = client.post(f"/continue-from-task/{parent_task_id}", data={}, follow_redirects=False)
    print("continue_response_status_code=", response.status_code, sep="")

    new_task = get_new_task(before_ids)

    print("new_continuation_task_found=", new_task is not None, sep="")

    if not new_task:
        print("new_paid_submit_started=False")
        print("RESULT=STAGE8_CONTINUE_BUTTON_FAILED_NO_NEW_TASK")
        return 1

    params = new_task.get("params") or {}
    refs = new_task.get("refs") or []

    print("new_task_id=", new_task.get("id"), sep="")
    print("new_task_status=", new_task.get("status"), sep="")
    print("new_task_model=", new_task.get("model"), sep="")
    print("new_task_continuation_mode=", params.get("continuation_mode"), sep="")
    print("new_task_parent_task_id=", params.get("parent_task_id"), sep="")
    print("new_task_parent_last_frame_path=", params.get("parent_last_frame_path"), sep="")
    print("new_task_return_last_frame=", params.get("return_last_frame"), sep="")
    print("new_task_refs_count=", len(refs), sep="")

    parent_frame_ref_ok = any(
        ref.get("role") == "parent_last_frame_reference"
        and ref.get("local_path") == str(last_frame)
        for ref in refs
    )

    print("parent_last_frame_ref_added=", parent_frame_ref_ok, sep="")
    print("new_paid_submit_started=False")

    ok = (
        index_response.status_code == 200
        and "Continue from previous take" in index_response.text
        and response.status_code == 200
        and new_task.get("status") == "queued"
        and new_task.get("model") == "seedance-2.0-fast"
        and params.get("continuation_mode") == "last_frame_as_reference"
        and int(params.get("parent_task_id")) == parent_task_id
        and params.get("parent_last_frame_path") == str(last_frame)
        and params.get("return_last_frame") is True
        and parent_frame_ref_ok
    )

    if ok:
        print("RESULT=STAGE8_CONTINUE_BUTTON_OK")
        return 0

    print("RESULT=STAGE8_CONTINUE_BUTTON_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
