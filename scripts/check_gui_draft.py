from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.main import app


def main() -> int:
    client = TestClient(app)

    health = client.get("/health")
    print("health_status_code=", health.status_code, sep="")
    print("available_models=", health.json().get("available_models"), sep="")

    index = client.get("/")
    print("index_status_code=", index.status_code, sep="")
    print("contains_seedance_fast=", "seedance-2.0-fast" in index.text, sep="")

    response = client.post(
        "/draft-task",
        data={
            "prompt": "Local GUI draft test only.",
            "model": "seedance-2.0-fast",
            "duration": "4",
            "resolution": "480p",
            "aspect_ratio": "16:9",
            "seed": "-1",
        },
        files=[],
    )

    print("draft_status_code=", response.status_code, sep="")
    print("contains_saved_message=", "Draft task saved locally" in response.text, sep="")
    print("contains_fast_model=", "seedance-2.0-fast" in response.text, sep="")
    print("contains_no_paid_generation=", "No paid generation was started" in response.text, sep="")

    if (
        health.status_code == 200
        and index.status_code == 200
        and response.status_code == 200
        and "seedance-2.0-fast" in index.text
        and "Draft task saved locally" in response.text
    ):
        print("RESULT=GUI_MODEL_SELECTOR_DRAFT_OK")
        return 0

    print("RESULT=GUI_MODEL_SELECTOR_DRAFT_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
