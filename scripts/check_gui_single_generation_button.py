from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.main import app


def main() -> int:
    client = TestClient(app)

    index = client.get("/")
    print("index_status_code=", index.status_code, sep="")
    print("contains_paid_button=", "Run Single Generation (paid)" in index.text, sep="")
    print("contains_run_endpoint=", "/run-single-generation" in index.text, sep="")
    print("contains_queue_later_text=", "queue comes later" in index.text, sep="")

    health = client.get("/health")
    print("health_status_code=", health.status_code, sep="")
    print("available_models=", health.json().get("available_models"), sep="")

    if (
        index.status_code == 200
        and health.status_code == 200
        and "Run Single Generation (paid)" in index.text
        and "/run-single-generation" in index.text
    ):
        print("RESULT=GUI_SINGLE_GENERATION_BUTTON_OK")
        return 0

    print("RESULT=GUI_SINGLE_GENERATION_BUTTON_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
