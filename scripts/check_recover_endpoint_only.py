from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.db import create_task, delete_task
from app.main import app


def main() -> int:
    print("=== Recover endpoint only check ===")

    params = {
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "recover_endpoint_test_no_generation",
    }

    task_id = create_task(
        model="seedance-2.0-fast",
        prompt="Recover endpoint smoke test. No generation.",
        params=params,
        refs=[],
        status="failed",
    )

    client = TestClient(app)
    response = client.post(f"/recover-task/{task_id}")

    print("task_id=", task_id, sep="")
    print("response_status_code=", response.status_code, sep="")
    print("contains_no_request_id=", "has no request_id" in response.text, sep="")
    print("contains_no_paid_submit=", "No new paid submit was started" in response.text, sep="")
    print("new_paid_submit_started=False")

    delete_task(task_id)

    if (
        response.status_code == 200
        and "has no request_id" in response.text
        and "No new paid submit was started" in response.text
    ):
        print("RESULT=RECOVER_ENDPOINT_ONLY_OK")
        return 0

    print("RESULT=RECOVER_ENDPOINT_ONLY_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
