from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.main import app


def main() -> int:
    print("=== GUI open path same-page check ===")

    client = TestClient(app)
    response = client.get("/")

    print("index_status_code=", response.status_code, sep="")
    print("contains_open_path_link_class=", "open-path-link" in response.text, sep="")
    print("contains_data_open_path=", "data-open-path=" in response.text, sep="")
    print("contains_fetch_open_path=", 'fetch("/open-path?path="' in response.text, sep="")
    print("contains_target_blank=", 'target="_blank"' in response.text, sep="")

    if (
        response.status_code == 200
        and "open-path-link" in response.text
        and "data-open-path=" in response.text
        and 'fetch("/open-path?path="' in response.text
        and 'target="_blank"' not in response.text
    ):
        print("RESULT=GUI_OPEN_PATH_SAME_PAGE_OK")
        return 0

    print("RESULT=GUI_OPEN_PATH_SAME_PAGE_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
