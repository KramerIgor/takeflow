from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.projects import (
    ACTIVE_PROJECT_FILE,
    get_active_project_dir,
    get_active_project_name,
    get_output_root,
    list_projects,
    set_active_project,
)


def main() -> int:
    print("=== Active project state check ===")

    output_root = get_output_root()
    previous_active = get_active_project_name()
    test_project_name = "_stage7_active_state_test"
    test_project_dir = output_root / test_project_name

    print("output_root=", output_root, sep="")
    print("previous_active_project=", previous_active, sep="")
    print("active_state_file=", ACTIVE_PROJECT_FILE, sep="")

    shutil.rmtree(test_project_dir, ignore_errors=True)

    try:
        state = set_active_project(test_project_name)

        active_after_set = get_active_project_name()
        active_dir_after_set = get_active_project_dir()

        projects = list_projects(root=output_root)
        test_project_rows = [item for item in projects if item["name"] == test_project_name]

        print("state_file_exists=", ACTIVE_PROJECT_FILE.exists(), sep="")
        print("state_active_project_name=", state.get("active_project_name"), sep="")
        print("active_after_set=", active_after_set, sep="")
        print("active_dir_after_set=", active_dir_after_set, sep="")
        print("test_project_dir_exists=", test_project_dir.exists(), sep="")
        print("test_project_inbox_exists=", (test_project_dir / "results" / "_inbox").exists(), sep="")
        print("test_project_visible_in_list=", bool(test_project_rows), sep="")
        print("test_project_marked_active=", bool(test_project_rows and test_project_rows[0]["is_active"]), sep="")

        ok_after_set = (
            ACTIVE_PROJECT_FILE.exists()
            and state.get("active_project_name") == test_project_name
            and active_after_set == test_project_name
            and active_dir_after_set == test_project_dir
            and test_project_dir.exists()
            and (test_project_dir / "results" / "_inbox").exists()
            and bool(test_project_rows)
            and bool(test_project_rows[0]["is_active"])
        )

    finally:
        restore_state = set_active_project(previous_active)
        shutil.rmtree(test_project_dir, ignore_errors=True)

    active_after_restore = get_active_project_name()

    print("restored_active_project=", active_after_restore, sep="")
    print("restore_state_active_project_name=", restore_state.get("active_project_name"), sep="")
    print("test_project_deleted=True")
    print("new_paid_submit_started=False")

    ok_restore = active_after_restore == previous_active

    if ok_after_set and ok_restore:
        print("RESULT=ACTIVE_PROJECT_STATE_OK")
        return 0

    print("RESULT=ACTIVE_PROJECT_STATE_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
