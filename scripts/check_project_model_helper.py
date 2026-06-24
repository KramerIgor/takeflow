from pathlib import Path
import shutil
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.projects import (
    create_project,
    get_active_project_name,
    get_output_root,
    list_projects,
    sanitize_project_name,
)


def main() -> int:
    print("=== Project model helper check ===")

    tmp = Path(tempfile.mkdtemp(prefix="seedance_projects_test_"))

    try:
        p1 = create_project("Psailor kun", root=tmp)
        p2 = create_project("Another<Project?>", root=tmp)

        projects = list_projects(root=tmp)
        names = [item["name"] for item in projects]

        print("current_output_root=", get_output_root(), sep="")
        print("current_active_project=", get_active_project_name(), sep="")
        print("tmp_project_1=", p1, sep="")
        print("tmp_project_2=", p2, sep="")
        print("sanitized_psailor=", sanitize_project_name("Psailor kun"), sep="")
        print("sanitized_another=", sanitize_project_name("Another<Project?>"), sep="")
        print("projects_count=", len(projects), sep="")
        print("project_names=", ",".join(names), sep="")
        print("project_1_inbox_exists=", (p1 / "results" / "_inbox").exists(), sep="")
        print("project_2_inbox_exists=", (p2 / "results" / "_inbox").exists(), sep="")
        print("new_paid_submit_started=False")

        ok = (
            sanitize_project_name("Psailor kun") == "Psailor_kun"
            and "Another_Project" in sanitize_project_name("Another<Project?>")
            and len(projects) == 2
            and (p1 / "results" / "_inbox").exists()
            and (p2 / "results" / "_inbox").exists()
            and get_active_project_name() == "Psailor_kun"
        )

        if ok:
            print("RESULT=PROJECT_MODEL_HELPER_OK")
            return 0

        print("RESULT=PROJECT_MODEL_HELPER_FAILED")
        return 1

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
