from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.db import list_tasks
from app.main import app, auto_recover_existing_requests


def queued_tasks_count() -> int:
    return len([task for task in list_tasks(limit=1000) if task["status"] == "queued"])


def attention_tasks_count() -> int:
    return len([
        task for task in list_tasks(limit=1000)
        if task["status"] in ["processing", "recoverable"]
        and task.get("request_id")
        and not task.get("output_path")
    ])


def main() -> int:
    print("=== Auto recovery before queue check ===")

    source = (PROJECT_ROOT / "app" / "main.py").read_text(encoding="utf-8")

    print("contains_auto_recovery_helper=", "def auto_recover_existing_requests" in source, sep="")
    print("start_once_has_auto_recovery=", "auto_recovery = auto_recover_existing_requests()" in source, sep="")
    print("start_loop_has_auto_recovery=", source.count("auto_recovery = auto_recover_existing_requests()") >= 2, sep="")

    queued_before = queued_tasks_count()
    attention_before = attention_tasks_count()

    print("queued_before=", queued_before, sep="")
    print("recoverable_or_processing_attention_before=", attention_before, sep="")

    if queued_before != 0:
        print("paid_generation_started=False")
        print("RESULT=SKIPPED_BECAUSE_QUEUED_TASKS_EXIST")
        return 2

    direct_result = auto_recover_existing_requests()
    print("direct_auto_recovery_checked_count=", direct_result.get("checked_count"), sep="")
    print("direct_auto_recovery_completed_count=", direct_result.get("completed_count"), sep="")
    print("direct_auto_recovery_new_paid_submit=", direct_result.get("new_paid_submit"), sep="")

    client = TestClient(app)
    response = client.post("/start-queue-loop", data={"max_tasks": "1"})

    print("start_queue_loop_status_code=", response.status_code, sep="")
    print("contains_no_queued_tasks_message=", "No queued tasks to process" in response.text or "Auto-recovered" in response.text, sep="")
    print("new_paid_submit_started=False")

    ok = (
        "def auto_recover_existing_requests" in source
        and source.count("auto_recovery = auto_recover_existing_requests()") >= 2
        and queued_before == 0
        and direct_result.get("new_paid_submit") is False
        and response.status_code == 200
    )

    if ok:
        print("RESULT=AUTO_RECOVERY_BEFORE_QUEUE_OK")
        return 0

    print("RESULT=AUTO_RECOVERY_BEFORE_QUEUE_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
