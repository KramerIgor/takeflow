from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.main import app


def main() -> int:
    print("=== GUI clickable output paths check ===")

    client = TestClient(app)

    index = client.get("/")
    print("index_status_code=", index.status_code, sep="")
    print("contains_open_result_folder=", "Open result folder" in index.text, sep="")
    print("contains_open_path_endpoint=", "/open-path?path=" in index.text, sep="")

    blocked = client.get("/open-path", params={"path": "/etc/passwd"})
    print("blocked_status_code=", blocked.status_code, sep="")
    print("blocked_outside_output=", "outside the configured output folder" in blocked.text, sep="")

    if (
        index.status_code == 200
        and "Open result folder" in index.text
        and "/open-path?path=" in index.text
        and blocked.status_code == 400
    ):
        print("RESULT=GUI_CLICKABLE_PATHS_OK")
        return 0

    print("RESULT=GUI_CLICKABLE_PATHS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
