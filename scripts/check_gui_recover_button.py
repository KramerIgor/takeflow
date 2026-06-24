from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.db import create_task, delete_task, update_task_fields
from app.main import app


def main() -> int:
    print("=== GUI recover button check ===")

    params = {
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "recover_button_ui_smoke_test_no_generation",
    }

    task_id = create_task(
        model="seedance-2.0-fast",
        prompt="Recover button UI smoke test. No generation.",
        params=params,
        refs=[],
        status="failed",
    )

    update_task_fields(
        task_id,
        status="failed",
        request_id="fake-request-id-for-ui-only",
        error="Synthetic UI test error",
    )

    client = TestClient(app)
    response = client.get("/")

    print("index_status_code=", response.status_code, sep="")
    print("test_failed_task_id=", task_id, sep="")
    print("contains_recover_button=", "Recover result" in response.text, sep="")
    print("contains_recover_endpoint=", f"/recover-task/{task_id}" in response.text, sep="")
    print("contains_no_new_paid_text=", "without a new paid submit" in response.text, sep="")

    delete_task(task_id)
    print("test_task_deleted=True")
    print("new_paid_submit_started=False")

    if (
        response.status_code == 200
        and "Recover result" in response.text
        and f"/recover-task/{task_id}" in response.text
        and "without a new paid submit" in response.text
    ):
        print("RESULT=GUI_RECOVER_BUTTON_OK")
        return 0

    print("RESULT=GUI_RECOVER_BUTTON_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
