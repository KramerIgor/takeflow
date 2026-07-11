from pathlib import Path
import os
import shutil
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

TEST_ROOT = Path(tempfile.mkdtemp(prefix="takeflow_add_queue_"))
os.environ["TAKEFLOW_DATA_DIR"] = str(TEST_ROOT / "data")
os.environ["OUTPUT_ROOT"] = str(TEST_ROOT / "outputs")
os.environ["OUTPUT_DIR"] = str(TEST_ROOT / "outputs" / "MyFirstProject")

from fastapi.testclient import TestClient
from app.db import list_tasks
from app.main import app


def main() -> int:
    try:
        client = TestClient(app)
        before_count = len(list_tasks(limit=1000))

        response = client.post(
            "/add-to-queue",
            data={
                "prompt": "Queue smoke test only. No generation.",
                "model": "seedance-2.0-fast",
                "duration": "4",
                "resolution": "480p",
                "aspect_ratio": "16:9",
                "seed": "-1",
            },
            files=[],
        )

        after_tasks = list_tasks(limit=1000)
        after_count = len(after_tasks)

        print("add_status_code=", response.status_code, sep="")
        print("before_count=", before_count, sep="")
        print("after_count=", after_count, sep="")
        print("contains_added_message=", "added to queue" in response.text, sep="")
        print("contains_internal_error=", "Internal Server Error" in response.text, sep="")

        newest = after_tasks[0] if after_tasks else None
        if newest:
            print("newest_task_id=", newest["id"], sep="")
            print("newest_task_status=", newest["status"], sep="")
            print("newest_task_model=", newest["model"], sep="")
            print("newest_task_mode=", newest["params"].get("mode"), sep="")

        if (
            response.status_code == 200
            and "Internal Server Error" not in response.text
            and after_count == before_count + 1
            and newest
            and newest["status"] == "queued"
            and newest["params"].get("mode") == "queued_no_generation_yet"
        ):
            print("new_paid_submit_started=False")
            print("RESULT=GUI_ADD_TO_QUEUE_OK")
            return 0

        print("RESULT=GUI_ADD_TO_QUEUE_FAILED")
        return 1
    finally:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
