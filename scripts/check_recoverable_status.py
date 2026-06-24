from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.db import create_task, delete_task, get_task, update_task_fields
from app.main import app


def main() -> int:
    print("=== Recoverable status check ===")

    params = {
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "recoverable_status_smoke_test_no_generation",
    }

    task_id = create_task(
        model="seedance-2.0-fast",
        prompt="Recoverable status UI smoke test. No generation.",
        params=params,
        refs=[],
        status="recoverable",
    )

    update_task_fields(
        task_id,
        status="recoverable",
        request_id="fake-request-id-for-ui-only",
        error="Synthetic recoverable UI test error",
    )

    task = get_task(task_id)

    client = TestClient(app)
    response = client.get("/")

    print("task_id=", task_id, sep="")
    print("task_status=", task["status"] if task else None, sep="")
    print("index_status_code=", response.status_code, sep="")
    print("contains_recoverable=", "recoverable" in response.text, sep="")
    print("contains_recover_button=", "Recover result" in response.text, sep="")
    print("contains_recover_endpoint=", f"/recover-task/{task_id}" in response.text, sep="")
    print("new_paid_submit_started=False")

    delete_task(task_id)
    print("test_task_deleted=True")

    if (
        task
        and task["status"] == "recoverable"
        and response.status_code == 200
        and "Recover result" in response.text
        and f"/recover-task/{task_id}" in response.text
    ):
        print("RESULT=RECOVERABLE_STATUS_OK")
        return 0

    print("RESULT=RECOVERABLE_STATUS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
