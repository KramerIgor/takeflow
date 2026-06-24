from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.main import app


def main() -> int:
    client = TestClient(app)

    health = client.get("/health")
    print("health_status_code=", health.status_code, sep="")
    print("health_json=", health.json(), sep="")

    page = client.get("/")
    print("index_status_code=", page.status_code, sep="")
    print("index_contains_seedance_gui=", "Seedance GUI" in page.text, sep="")
    print("index_contains_prompt=", "Prompt" in page.text, sep="")
    print("index_contains_reference_images=", "Reference images" in page.text, sep="")

    if health.status_code == 200 and page.status_code == 200 and "Seedance GUI" in page.text:
        print("RESULT=GUI_SKELETON_OK")
        return 0

    print("RESULT=GUI_SKELETON_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
