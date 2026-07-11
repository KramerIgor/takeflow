from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.main import app
from app.projects import get_active_project_name, get_output_root


def main() -> int:
    print("=== GUI create-project check ===")

    test_project_name = "_stage7_ui_create_test"
    output_root = get_output_root()
    active_project_name = get_active_project_name()
    test_project_dir = output_root / test_project_name

    if test_project_dir.exists():
        shutil.rmtree(test_project_dir, ignore_errors=True)

    client = TestClient(app)

    index_before = client.get("/")
    response = client.post("/create-project", data={"project_name": test_project_name})
    index_after = client.get("/")

    print("output_root=", output_root, sep="")
    print("test_project_dir=", test_project_dir, sep="")
    print("index_before_status_code=", index_before.status_code, sep="")
    print("create_response_status_code=", response.status_code, sep="")
    print("index_after_status_code=", index_after.status_code, sep="")
    print("project_dir_exists_after_create=", test_project_dir.exists(), sep="")
    print("project_inbox_exists_after_create=", (test_project_dir / "results" / "_inbox").exists(), sep="")
    print("contains_create_project_form=", "Create project folder" in index_after.text, sep="")
    print("contains_test_project_in_list=", test_project_name in index_after.text, sep="")
    print("contains_active_project=", active_project_name in index_after.text, sep="")
    print("new_paid_submit_started=False")

    ok = (
        index_before.status_code == 200
        and response.status_code == 200
        and index_after.status_code == 200
        and test_project_dir.exists()
        and (test_project_dir / "results" / "_inbox").exists()
        and "Create project folder" in index_after.text
        and test_project_name in index_after.text
        and active_project_name in index_after.text
    )

    shutil.rmtree(test_project_dir, ignore_errors=True)
    print("test_project_deleted=True")

    if ok:
        print("RESULT=GUI_CREATE_PROJECT_OK")
        return 0

    print("RESULT=GUI_CREATE_PROJECT_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
