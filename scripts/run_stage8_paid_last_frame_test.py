from pathlib import Path
import json
import sys
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app.main as main
from app.db import list_tasks
from app.projects import get_active_project_name, get_active_project_dir
from app.last_frame import collect_last_frame_candidates, last_frame_status_payload


TEST_EPISODE = "Episode_00"
TEST_SCENE = "Scene_998_LastFrame_API_Test"

PROMPT = (
    "A simple high-quality 2D anime shot of a quiet empty city street at sunset, "
    "soft warm light, no characters, slow cinematic camera movement, clean composition."
)


def get_task_by_id(task_id: int) -> dict | None:
    for task in list_tasks(limit=1000):
        if int(task["id"]) == int(task_id):
            return task

    return None


def find_new_task(before_ids: set[int]) -> dict | None:
    new_tasks = [
        task for task in list_tasks(limit=1000)
        if int(task["id"]) not in before_ids
    ]

    if not new_tasks:
        return None

    return sorted(new_tasks, key=lambda task: int(task["id"]), reverse=True)[0]


def find_result_response(run_dir: Path) -> Path | None:
    candidates = [
        run_dir / "result_response.json",
        run_dir / "recovery_result_response.json",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def print_json_keys(path: Path) -> dict | None:
    if not path.exists():
        print(f"{path.name}_exists=False")
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"{path.name}_read_error={type(exc).__name__}: {exc}")
        return None

    print(f"{path.name}_exists=True")
    print(f"{path.name}_top_level_keys={sorted(data.keys()) if isinstance(data, dict) else type(data).__name__}")

    return data


def main_run() -> int:
    print("=== Stage 8 paid last-frame test ===")
    print("active_project_name=", get_active_project_name(), sep="")
    print("active_project_dir=", get_active_project_dir(), sep="")
    print("test_episode=", TEST_EPISODE, sep="")
    print("test_scene=", TEST_SCENE, sep="")
    print("return_last_frame=True")
    print("new_paid_submit_will_start=True")

    client = TestClient(main.app)

    before_ids = {int(task["id"]) for task in list_tasks(limit=1000)}
    print("tasks_before=", len(before_ids), sep="")

    add_response = client.post(
        "/add-to-queue",
        data={
            "prompt": PROMPT,
            "model": "seedance-2.0",
            "duration": "4",
            "resolution": "480p",
            "aspect_ratio": "16:9",
            "seed": "",
            "episode_name": TEST_EPISODE,
            "scene_name": TEST_SCENE,
            "return_last_frame": "1",
        },
        follow_redirects=False,
    )

    print("add_response_status_code=", add_response.status_code, sep="")

    task = find_new_task(before_ids)

    if not task:
        print("new_task_found=False")
        print("RESULT=STAGE8_PAID_LAST_FRAME_TEST_FAILED_NO_TASK")
        return 1

    task_id = int(task["id"])
    params = task.get("params") or {}

    print("new_task_found=True")
    print("task_id=", task_id, sep="")
    print("task_initial_status=", task.get("status"), sep="")
    print("task_project_name=", params.get("project_name"), sep="")
    print("task_episode_name=", params.get("episode_name"), sep="")
    print("task_scene_name=", params.get("scene_name"), sep="")
    print("task_return_last_frame=", params.get("return_last_frame"), sep="")

    print()
    print("=== Starting queue once: PAID SUBMIT EXPECTED ===")
    start_response = client.post(
        "/start-queue-once",
        data={},
        follow_redirects=False,
    )

    print("start_response_status_code=", start_response.status_code, sep="")

    task_after = get_task_by_id(task_id)

    if not task_after:
        print("processed_task_found=False")
        print("RESULT=STAGE8_PAID_LAST_FRAME_TEST_FAILED_TASK_DISAPPEARED")
        return 1

    print("processed_task_found=True")
    print("processed_task_status=", task_after.get("status"), sep="")
    print("request_id=", task_after.get("request_id"), sep="")
    print("output_path=", task_after.get("output_path"), sep="")
    print("error_message=", task_after.get("error_message"), sep="")

    output_path_raw = task_after.get("output_path")

    if not output_path_raw:
        print("output_path_found=False")
        print("RESULT=STAGE8_PAID_LAST_FRAME_TEST_FAILED_NO_OUTPUT")
        return 1

    output_path = Path(output_path_raw)
    print("output_path_exists=", output_path.exists(), sep="")

    if output_path.parent.name == "videos":
        run_dir = output_path.parent.parent / "runs" / output_path.stem
    else:
        run_dir = output_path.parent

    print("run_dir=", run_dir, sep="")
    print("run_dir_exists=", run_dir.exists(), sep="")

    technical_output = run_dir / "output.mp4"
    last_frame_path = run_dir / "last_frame.png"
    summary_path = run_dir / "summary.json"
    status_path = run_dir / "status.json"

    print("technical_output_exists=", technical_output.exists(), sep="")
    print("last_frame_png_exists=", last_frame_path.exists(), sep="")
    print("last_frame_png_size=", last_frame_path.stat().st_size if last_frame_path.exists() else 0, sep="")
    print("summary_json_exists=", summary_path.exists(), sep="")
    print("status_json_exists=", status_path.exists(), sep="")

    result_response_path = find_result_response(run_dir)

    if result_response_path:
        print("result_response_path=", result_response_path, sep="")
        result_data = print_json_keys(result_response_path)
    else:
        print("result_response_path=None")
        result_data = None

    print()
    print("=== API last-frame candidate scan ===")

    if result_data is not None:
        candidates = collect_last_frame_candidates(result_data)
        status_payload = last_frame_status_payload(result_data)

        print("api_last_frame_candidates_count=", len(candidates), sep="")
        print("api_last_frame_found=", status_payload.get("last_frame_found"), sep="")
        print("api_last_frame_url=", status_payload.get("last_frame_url"), sep="")
        print("api_last_frame_key_path=", status_payload.get("last_frame_key_path"), sep="")
        print("api_last_frame_candidate_score=", status_payload.get("last_frame_candidate_score"), sep="")
        print("api_last_frame_candidate_reason=", status_payload.get("last_frame_candidate_reason"), sep="")

        for index, candidate in enumerate(candidates[:10], start=1):
            print("---")
            print(f"candidate_{index}_score={candidate.score}")
            print(f"candidate_{index}_key_path={candidate.key_path}")
            print(f"candidate_{index}_reason={candidate.reason}")
            print(f"candidate_{index}_url={candidate.url}")
    else:
        print("api_last_frame_candidates_count=0")
        print("api_last_frame_found=False")

    print()
    print("=== Summary/status last-frame fields ===")

    summary = print_json_keys(summary_path) if summary_path.exists() else None
    status = print_json_keys(status_path) if status_path.exists() else None

    if isinstance(summary, dict):
        for key in [
            "last_frame_found",
            "last_frame_source",
            "last_frame_url",
            "last_frame_path",
            "last_frame_key_path",
            "last_frame_candidate_score",
            "last_frame_candidate_reason",
            "video_path",
            "technical_output_path",
        ]:
            print(f"summary_{key}={summary.get(key)}")

    if isinstance(status, dict):
        for key in [
            "last_frame_found",
            "last_frame_source",
            "last_frame_url",
            "last_frame_path",
            "last_frame_key_path",
        ]:
            print(f"status_{key}={status.get(key)}")

    print()
    print("new_paid_submit_started=True")

    if task_after.get("status") == "completed" and last_frame_path.exists() and last_frame_path.stat().st_size > 0:
        print("RESULT=STAGE8_PAID_LAST_FRAME_TEST_OK_API_FRAME_SAVED")
        return 0

    if task_after.get("status") == "completed":
        print("RESULT=STAGE8_PAID_LAST_FRAME_TEST_COMPLETED_NO_LAST_FRAME_SAVED")
        return 0

    print("RESULT=STAGE8_PAID_LAST_FRAME_TEST_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
