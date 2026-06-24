from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import list_tasks
from app.queue_worker import process_queue_loop


def queued_tasks_count() -> int:
    return len([task for task in list_tasks(limit=1000) if task["status"] == "queued"])


def main() -> int:
    print("=== Worker console logs no-task check ===")

    queued_before = queued_tasks_count()
    print("queued_before=", queued_before, sep="")

    if queued_before != 0:
        print("paid_generation_started=False")
        print("RESULT=SKIPPED_BECAUSE_QUEUED_TASKS_EXIST")
        return 2

    buffer = StringIO()

    with redirect_stdout(buffer):
        result = process_queue_loop(dry_run=False, max_tasks=2, stop_on_failure=True)

    captured = buffer.getvalue()

    print("captured_log_begin")
    print(captured.strip())
    print("captured_log_end")

    print("worker_processed_count=", result.get("processed_count"), sep="")
    print("worker_stopped_reason=", result.get("stopped_reason"), sep="")
    print("contains_queue_log=", "[QUEUE]" in captured, sep="")
    print("contains_no_queued_tasks=", "no queued tasks" in captured, sep="")
    print("paid_generation_started=False")

    if (
        result.get("processed_count") == 0
        and result.get("stopped_reason") == "no_queued_tasks"
        and "[QUEUE]" in captured
        and "no queued tasks" in captured
    ):
        print("RESULT=WORKER_CONSOLE_LOGS_OK")
        return 0

    print("RESULT=WORKER_CONSOLE_LOGS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
