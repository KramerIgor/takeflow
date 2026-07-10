from pathlib import Path
import os
import sys
import tempfile

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import main
from app import projects as projects_module


def main_check() -> int:
    print("=== Output root selector check ===")

    previous_output_root = os.environ.get("OUTPUT_ROOT")
    previous_active_project_file = projects_module.ACTIVE_PROJECT_FILE
    previous_update_env_values = main.update_env_values

    captured_updates: dict[str, str] = {}

    def fake_update_env_values(values: dict[str, str]) -> None:
        captured_updates.update(values)

    with tempfile.TemporaryDirectory(prefix="takeflow_output_root_check_") as tmp:
        tmp_root = Path(tmp)
        initial_root = tmp_root / "initial_root"
        selected_root = tmp_root / "selected_root"
        projects_module.ACTIVE_PROJECT_FILE = tmp_root / "data" / "active_project.json"
        main.update_env_values = fake_update_env_values
        os.environ["OUTPUT_ROOT"] = str(initial_root)

        try:
            projects_module.set_active_project("Demo_Project")
            client = TestClient(main.app)

            page = client.get("/")
            has_form = 'action="/update-output-root"' in page.text
            has_picker_button = "data-output-root-picker" in page.text
            has_root_label = "Output root" in page.text
            has_picker_route = any(route.path == "/choose-output-root" for route in main.app.routes)

            response = client.post("/update-output-root", data={"output_root_path": str(selected_root)})
            selected_active_dir = projects_module.get_active_project_dir()

            valid_saved = (
                response.status_code == 200
                and os.environ.get("OUTPUT_ROOT") == str(selected_root)
                and captured_updates.get("OUTPUT_ROOT") == str(selected_root)
                and selected_root.exists()
                and selected_active_dir == selected_root / "Demo_Project"
                and selected_active_dir.exists()
            )

            invalid_response = client.post("/update-output-root", data={"output_root_path": "relative-folder"})
            invalid_rejected = (
                invalid_response.status_code == 200
                and "Output root was not changed" in invalid_response.text
                and os.environ.get("OUTPUT_ROOT") == str(selected_root)
            )

            print("has_output_root_form=", has_form, sep="")
            print("has_output_root_label=", has_root_label, sep="")
            print("has_output_root_picker_button=", has_picker_button, sep="")
            print("has_output_root_picker_route=", has_picker_route, sep="")
            print("valid_root_saved=", valid_saved, sep="")
            print("invalid_relative_rejected=", invalid_rejected, sep="")
            print("selected_active_dir=", selected_active_dir, sep="")

            if has_form and has_picker_button and has_root_label and has_picker_route and valid_saved and invalid_rejected:
                print("RESULT=OUTPUT_ROOT_SELECTOR_OK")
                return 0

            print("RESULT=OUTPUT_ROOT_SELECTOR_FAILED")
            return 1

        finally:
            main.update_env_values = previous_update_env_values
            projects_module.ACTIVE_PROJECT_FILE = previous_active_project_file
            if previous_output_root is None:
                os.environ.pop("OUTPUT_ROOT", None)
            else:
                os.environ["OUTPUT_ROOT"] = previous_output_root


if __name__ == "__main__":
    raise SystemExit(main_check())
