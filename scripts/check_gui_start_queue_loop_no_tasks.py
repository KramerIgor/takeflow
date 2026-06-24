from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.db import list_tasks
from app.main import app


def queued_tasks_count() -> int:
    return len([task for task in list_tasks(limit=1000) if task["status"] == "queued"])


def main() -> int:
    print("=== GUI Start Queue Loop no-task smoke test ===")

    client = TestClient(app)

    index = client.get("/")
    print("index_status_code=", index.status_code, sep="")
    print("contains_queue_loop_button=", "Start Queue Loop (paid)" in index.text, sep="")
    print("contains_queue_loop_endpoint=", "/start-queue-loop" in index.text, sep="")
    print("contains_max_tasks_input=", 'name="max_tasks"' in index.text, sep="")

    queued_before = queued_tasks_count()
    print("queued_before=", queued_before, sep="")

    if queued_before != 0:
        print("paid_generation_started=False")
        print("RESULT=SKIPPED_BECAUSE_QUEUED_TASKS_EXIST")
        return 2

    response = client.post("/start-queue-loop", data={"max_tasks": "2"})

    queued_after = queued_tasks_count()

    print("loop_status_code=", response.status_code, sep="")
    print("contains_no_tasks_message=", "No queued tasks to process" in response.text, sep="")
    print("contains_no_paid_message=", "No paid generation was started" in response.text, sep="")
    print("queued_after=", queued_after, sep="")
    print("paid_generation_started=False")

    if (
        index.status_code == 200
        and response.status_code == 200
        and "Start Queue Loop (paid)" in index.text
        and "/start-queue-loop" in index.text
        and "No queued tasks to process" in response.text
        and queued_after == 0
    ):
        print("RESULT=GUI_START_QUEUE_LOOP_NO_TASKS_OK")
        return 0

    print("RESULT=GUI_START_QUEUE_LOOP_NO_TASKS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
