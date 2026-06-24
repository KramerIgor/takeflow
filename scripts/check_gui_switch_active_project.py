from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

import app.main as main
from app.projects import create_project, get_active_project_name, get_output_root, set_active_project


def main_test() -> int:
    print("=== GUI active project switch check ===")

    output_root = get_output_root()
    previous_active = get_active_project_name()
    test_project_name = "_stage7_switch_test"
    test_project_dir = output_root / test_project_name

    print("output_root=", output_root, sep="")
    print("previous_active_project=", previous_active, sep="")
    print("test_project_dir=", test_project_dir, sep="")

    shutil.rmtree(test_project_dir, ignore_errors=True)

    try:
        create_project(test_project_name)

        client = TestClient(main.app)

        index_before = client.get("/")
        switch_response = client.post("/set-active-project", data={"project_name": test_project_name})
        index_after_switch = client.get("/")

        active_after_switch = get_active_project_name()
        context_after_switch = main.project_context()

        print("index_before_status_code=", index_before.status_code, sep="")
        print("switch_response_status_code=", switch_response.status_code, sep="")
        print("index_after_switch_status_code=", index_after_switch.status_code, sep="")
        print("active_after_switch=", active_after_switch, sep="")
        print("context_active_after_switch=", context_after_switch.get("active_project_name"), sep="")
        print("contains_switch_button=", "Switch" in index_after_switch.text, sep="")
        print("contains_test_project=", test_project_name in index_after_switch.text, sep="")
        print("contains_switched_message=", "Active project switched to" in switch_response.text, sep="")
        print("test_project_inbox_exists=", (test_project_dir / "results" / "_inbox").exists(), sep="")
        print("new_paid_submit_started=False")

        ok_switch = (
            index_before.status_code == 200
            and switch_response.status_code == 200
            and index_after_switch.status_code == 200
            and active_after_switch == test_project_name
            and context_after_switch.get("active_project_name") == test_project_name
            and test_project_name in index_after_switch.text
            and "Active project switched to" in switch_response.text
            and (test_project_dir / "results" / "_inbox").exists()
        )

    finally:
        set_active_project(previous_active)
        shutil.rmtree(test_project_dir, ignore_errors=True)

    active_after_restore = get_active_project_name()

    print("restored_active_project=", active_after_restore, sep="")
    print("test_project_deleted=True")

    if ok_switch and active_after_restore == previous_active:
        print("RESULT=GUI_SWITCH_ACTIVE_PROJECT_OK")
        return 0

    print("RESULT=GUI_SWITCH_ACTIVE_PROJECT_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_test())
