from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.db import create_task, delete_task, get_task, list_tasks
from app.main import app


def main() -> int:
    print("=== Retry failed button check ===")

    params = {
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "retry_button_smoke_test_no_generation",
    }

    failed_task_id = create_task(
        model="seedance-2.0-fast",
        prompt="Retry failed smoke test. No generation.",
        params=params,
        refs=[],
        status="failed",
    )

    client = TestClient(app)

    index = client.get("/")
    print("index_status_code=", index.status_code, sep="")
    print("failed_task_id=", failed_task_id, sep="")
    print("contains_retry_button=", "Retry failed" in index.text, sep="")
    print("contains_retry_endpoint=", f"/retry-task/{failed_task_id}" in index.text, sep="")

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
    print("new_paid_submit_started=False")

    new_task_id = newest["id"] if newest else None

    if new_task_id:
        delete_task(new_task_id)

    delete_task(failed_task_id)
    print("test_tasks_deleted=True")

    ok = (
        index.status_code == 200
        and "Retry failed" in index.text
        and f"/retry-task/{failed_task_id}" in index.text
        and response.status_code == 200
        and after_count == before_count + 1
        and newest
        and newest["status"] == "queued"
        and newest["params"].get("mode") == "retry_queued_no_generation_yet"
        and newest["params"].get("retry_of_task_id") == failed_task_id
        and "No new paid submit was started" in response.text
    )

    if ok:
        print("RESULT=RETRY_FAILED_BUTTON_OK")
        return 0

    print("RESULT=RETRY_FAILED_BUTTON_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
