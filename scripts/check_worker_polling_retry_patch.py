from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import list_tasks
from app.queue_worker import process_queue_loop


def queued_tasks_count() -> int:
    return len([task for task in list_tasks(limit=1000) if task["status"] == "queued"])


def main() -> int:
    print("=== Worker polling retry patch check ===")

    worker_path = PROJECT_ROOT / "app" / "queue_worker.py"
    text = worker_path.read_text(encoding="utf-8")

    print("contains_network_retry_counter=", "transient_network_error_count" in text, sep="")
    print("contains_max_network_errors=", "max_transient_network_errors = 6" in text, sep="")
    print("contains_last_polling_error_file=", "last_polling_network_error.json" in text, sep="")
    print("contains_polling_network_error_log=", "polling network error" in text, sep="")

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
        "transient_network_error_count" in text
        and "max_transient_network_errors = 6" in text
        and "last_polling_network_error.json" in text
        and "polling network error" in text
        and queued_before == 0
        and result.get("processed_count") == 0
        and result.get("stopped_reason") == "no_queued_tasks"
    )

    if ok:
        print("RESULT=WORKER_POLLING_RETRY_PATCH_OK")
        return 0

    print("RESULT=WORKER_POLLING_RETRY_PATCH_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
