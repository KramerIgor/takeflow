from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import list_tasks
from app.queue_worker import process_next_queued_task_real


def main() -> int:
    print("=== Real queue worker no-task check ===")

    queued_before = [task for task in list_tasks(limit=1000) if task["status"] == "queued"]
    print(f"queued_before={len(queued_before)}")

    result = process_next_queued_task_real()

    print(f"worker_processed={result.get('processed')}")
    print(f"worker_reason={result.get('reason')}")
    print("paid_generation_started=False")

    queued_after = [task for task in list_tasks(limit=1000) if task["status"] == "queued"]
    print(f"queued_after={len(queued_after)}")

    if len(queued_before) == 0 and result.get("processed") is False and result.get("reason") == "no_queued_tasks":
        print("RESULT=REAL_QUEUE_WORKER_READY_NO_TASKS")
        return 0

    print("RESULT=CHECK_UNCLEAR")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
