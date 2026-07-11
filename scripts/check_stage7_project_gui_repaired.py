from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

import app.main as main
from app.projects import get_output_root


def main_test() -> int:
    print("=== Stage 7 repaired project GUI check ===")

    output_root = get_output_root()
    active_project_name = main.project_context().get("active_project_name", "")
    test_project_name = "_stage7_ui_create_test"
    test_project_dir = output_root / test_project_name

    shutil.rmtree(test_project_dir, ignore_errors=True)

    print("has_projects_module=", "projects_module" in main.__dict__, sep="")
    print("has_project_context=", "project_context" in main.__dict__, sep="")
    print("project_context_ok=", isinstance(main.project_context(), dict), sep="")
    print("project_context_active=", main.project_context().get("active_project_name"), sep="")
    print("project_context_output_root=", main.project_context().get("output_root"), sep="")

    client = TestClient(main.app)

    index_before = client.get("/")
    create_response = client.post("/create-project", data={"project_name": test_project_name})
    index_after = client.get("/")

    print("index_before_status_code=", index_before.status_code, sep="")
    print("create_response_status_code=", create_response.status_code, sep="")
    print("index_after_status_code=", index_after.status_code, sep="")

    print("project_dir_exists_after_create=", test_project_dir.exists(), sep="")
    print("project_inbox_exists_after_create=", (test_project_dir / "results" / "_inbox").exists(), sep="")

    print("contains_active_project_label=", "Active project:" in index_after.text, sep="")
    print("contains_active_project=", active_project_name in index_after.text, sep="")
    print("contains_output_root=", "C:\\AI_OUTPUT" in index_after.text or "/mnt/c/AI_OUTPUT" in index_after.text, sep="")
    print("contains_create_project_form=", "Create project folder" in index_after.text, sep="")
    print("contains_test_project_in_list=", test_project_name in index_after.text, sep="")
    print("contains_created_message=", "was created in the output root" in create_response.text, sep="")
    print("new_paid_submit_started=False")

    ok = (
        index_before.status_code == 200
        and create_response.status_code == 200
        and index_after.status_code == 200
        and test_project_dir.exists()
        and (test_project_dir / "results" / "_inbox").exists()
        and "Active project:" in index_after.text
        and active_project_name in index_after.text
        and "Create project folder" in index_after.text
        and test_project_name in index_after.text
        and "was created in the output root" in create_response.text
    )

    shutil.rmtree(test_project_dir, ignore_errors=True)
    print("test_project_deleted=True")

    if ok:
        print("RESULT=STAGE7_PROJECT_GUI_REPAIRED_OK")
        return 0

    print("RESULT=STAGE7_PROJECT_GUI_REPAIRED_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_test())
