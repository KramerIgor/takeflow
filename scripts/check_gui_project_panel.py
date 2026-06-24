from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.main import app


def main() -> int:
    print("=== GUI project panel check ===")

    client = TestClient(app)
    response = client.get("/")

    print("index_status_code=", response.status_code, sep="")
    print("contains_project_panel_title=", ">Project<" in response.text or "Project</h2>" in response.text, sep="")
    print("contains_active_project_label=", "Active project:" in response.text, sep="")
    print("contains_psailor_kun=", "Psailor_kun" in response.text, sep="")
    print("contains_output_root=", "C:\\AI_OUTPUT" in response.text or "/mnt/c/AI_OUTPUT" in response.text, sep="")
    print("contains_stage7_hint=", "Project switching and project creation will be added in Stage 7" in response.text, sep="")
    print("new_paid_submit_started=False")

    ok = (
        response.status_code == 200
        and "Active project:" in response.text
        and "Psailor_kun" in response.text
        and ("C:\\AI_OUTPUT" in response.text or "/mnt/c/AI_OUTPUT" in response.text)
        and "Project switching and project creation will be added in Stage 7" in response.text
    )

    if ok:
        print("RESULT=GUI_PROJECT_PANEL_OK")
        return 0

    print("RESULT=GUI_PROJECT_PANEL_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
