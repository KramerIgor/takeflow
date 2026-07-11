from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.db import create_task, delete_task, update_task_fields
from app.main import app
from app.projects import get_active_project_dir, get_active_project_name


def main() -> int:
    print("=== GUI output path visibility check ===")

    params = {
        "project_name": get_active_project_name(),
        "project_dir": str(get_active_project_dir()),
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "ui_path_smoke_test_no_generation",
    }

    task_id = create_task(
        model="seedance-2.0-fast",
        prompt="UI path smoke test only. No generation.",
        params=params,
        refs=[],
        status="completed",
    )

    update_task_fields(
        task_id,
        status="completed",
        output_path="/mnt/c/AI_OUTPUT/Example_project/fake_check/output.mp4",
        run_dir="/mnt/c/AI_OUTPUT/Example_project/fake_check",
        elapsed_total_seconds=1,
    )

    client = TestClient(app)
    response = client.get("/")

    contains_windows_output = "C:\\AI_OUTPUT\\Example_project\\fake_check\\output.mp4" in response.text
    contains_output_label = "Output video:" in response.text or "Выходное видео:" in response.text

    print("index_status_code=", response.status_code, sep="")
    print("test_task_id=", task_id, sep="")
    print("contains_windows_output=", contains_windows_output, sep="")
    print("contains_output_label=", contains_output_label, sep="")

    delete_task(task_id)
    print("test_task_deleted=True")

    if response.status_code == 200 and contains_windows_output and contains_output_label:
        print("RESULT=GUI_OUTPUT_PATHS_OK")
        return 0

    print("RESULT=GUI_OUTPUT_PATHS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
