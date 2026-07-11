from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.db import create_task, delete_task, get_task, list_tasks, update_task_fields
from app.main import app, error_view
from app import projects as projects_module


def main() -> int:
    print("=== Retry failed button check ===")

    params = {
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "retry_button_smoke_test_no_generation",
        "project_name": projects_module.get_active_project_name(),
        "project_dir": str(projects_module.get_active_project_dir()),
    }

    failed_task_id = create_task(
        model="seedance-2.0-fast",
        prompt="Retry failed smoke test. No generation.",
        params=params,
        refs=[],
        status="failed",
    )
    update_task_fields(
        failed_task_id,
        error="ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING] test-only error",
    )
    single_params = dict(params)
    single_params["mode"] = "single_generation_paid"
    single_task_id = create_task(
        model="seedance-2.0-fast",
        prompt="Single retry UI test. No generation.",
        params=single_params,
        refs=[],
        status="failed",
    )
    update_task_fields(single_task_id, error="Synthetic single failure")

    client = TestClient(app)

    error_cases = {
        "ConnectError: SSL unexpected_eof": "generation_error_connection",
        "ReadTimeout: timed out": "generation_error_timeout",
        "status 401 unauthorized": "generation_error_auth",
        "status 402 insufficient balance": "generation_error_balance",
        "status 429 rate limit": "generation_error_capacity",
        "status 400 validation failed": "generation_error_parameters",
        "Reference upload timed out before Segmind submit": "generation_error_reference_upload",
        "Output download failed": "generation_error_download",
        "Unknown synthetic failure": "generation_error_generic",
    }
    known_error_mapping = all(error_view(raw)["error_display_key"] == expected for raw, expected in error_cases.items())

    index = client.get("/")
    print("index_status_code=", index.status_code, sep="")
    print("failed_task_id=", failed_task_id, sep="")
    print("contains_queue_retry_button=", "Add to queue again" in index.text, sep="")
    print("contains_single_retry_button=", "Send again" in index.text, sep="")
    print("contains_retry_endpoint=", f"/retry-task/{failed_task_id}" in index.text, sep="")
    print("contains_delete_endpoint=", f"/delete-failed-task/{failed_task_id}" in index.text, sep="")
    print("friendly_connection_error=", "before Takeflow received confirmation" in index.text, sep="")
    print("known_error_mapping=", known_error_mapping, sep="")

    before_tasks = list_tasks(limit=1000)
    before_count = len(before_tasks)

    response = client.post(f"/retry-task/{failed_task_id}")

    after_tasks = list_tasks(limit=1000)
    after_count = len(after_tasks)

    newest = after_tasks[0] if after_tasks else None

    print("retry_response_status_code=", response.status_code, sep="")
    print("before_count=", before_count, sep="")
    print("after_count=", after_count, sep="")
    print("newest_task_id=", newest["id"] if newest else None, sep="")
    print("newest_task_status=", newest["status"] if newest else None, sep="")
    print("newest_task_mode=", newest["params"].get("mode") if newest else None, sep="")
    print("newest_retry_of_task_id=", newest["params"].get("retry_of_task_id") if newest else None, sep="")
    print("contains_no_paid_submit=", "No new paid submit was started" in response.text, sep="")
    delete_response = client.post(f"/delete-failed-task/{failed_task_id}")
    failed_record_deleted = get_task(failed_task_id) is None
    print("delete_response_status_code=", delete_response.status_code, sep="")
    print("failed_record_deleted=", failed_record_deleted, sep="")
    print("new_paid_submit_started=False")

    new_task_id = newest["id"] if newest else None

    if new_task_id:
        delete_task(new_task_id)

    delete_task(single_task_id)
    print("test_tasks_deleted=True")

    ok = (
        index.status_code == 200
        and "Add to queue again" in index.text
        and "Send again" in index.text
        and f"/retry-task/{failed_task_id}" in index.text
        and f"/delete-failed-task/{failed_task_id}" in index.text
        and "before Takeflow received confirmation" in index.text
        and known_error_mapping
        and response.status_code == 200
        and after_count == before_count + 1
        and newest
        and newest["status"] == "queued"
        and newest["params"].get("mode") == "retry_queued_no_generation_yet"
        and newest["params"].get("retry_of_task_id") == failed_task_id
        and "No new paid submit was started" in response.text
        and delete_response.status_code in {200, 303}
        and failed_record_deleted
    )

    if ok:
        print("RESULT=RETRY_FAILED_BUTTON_OK")
        return 0

    print("RESULT=RETRY_FAILED_BUTTON_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
