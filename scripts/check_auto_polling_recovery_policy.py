from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import list_tasks
from app.queue_worker import process_queue_loop


def queued_tasks_count() -> int:
    return len([task for task in list_tasks(limit=1000) if task["status"] == "queued"])


def main() -> int:
    print("=== Automatic polling recovery policy check ===")

    worker_path = PROJECT_ROOT / "app" / "queue_worker.py"
    text = worker_path.read_text(encoding="utf-8")

    print("contains_30_network_retries=", "max_transient_network_errors = 30" in text, sep="")
    print("contains_auto_retry_message=", "will retry automatically" in text, sep="")
    print("contains_recoverable_fallback=", "Task will become recoverable" in text, sep="")
    print("contains_recoverable_status=", 'status_to_set = "recoverable" if request_id else "failed"' in text, sep="")

    queued_before = queued_tasks_count()
    print("queued_before=", queued_before, sep="")

    if queued_before != 0:
        print("paid_generation_started=False")
        print("RESULT=SKIPPED_BECAUSE_QUEUED_TASKS_EXIST")
        return 2

    result = process_queue_loop(dry_run=False, max_tasks=1, stop_on_failure=True)

    print("worker_processed_count=", result.get("processed_count"), sep="")
    print("worker_stopped_reason=", result.get("stopped_reason"), sep="")
    print("paid_generation_started=False")

    ok = (
        "max_transient_network_errors = 30" in text
        and "will retry automatically" in text
        and "Task will become recoverable" in text
        and 'status_to_set = "recoverable" if request_id else "failed"' in text
        and queued_before == 0
        and result.get("processed_count") == 0
        and result.get("stopped_reason") == "no_queued_tasks"
    )

    if ok:
        print("RESULT=AUTO_POLLING_RECOVERY_POLICY_OK")
        return 0

    print("RESULT=AUTO_POLLING_RECOVERY_POLICY_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
