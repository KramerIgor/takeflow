from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import create_task, delete_task, get_task, list_tasks, update_task_fields
from app.main import cleanup_processing_without_request_id


def main() -> int:
    print("=== Stale processing cleanup check ===")

    params = {
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "stale_processing_cleanup_smoke_test_no_generation",
    }

    task_id = create_task(
        model="seedance-2.0-fast",
        prompt="Stale processing cleanup smoke test. No generation.",
        params=params,
        refs=[],
        status="queued",
    )

    update_task_fields(
        task_id,
        status="processing",
        request_id=None,
        error=None,
    )

    before = get_task(task_id)
    print("task_id=", task_id, sep="")
    print("status_before=", before["status"] if before else None, sep="")
    print("request_id_before=", before.get("request_id") if before else None, sep="")

    result = cleanup_processing_without_request_id()

    after = get_task(task_id)
    print("cleanup_checked_count=", result.get("checked_count"), sep="")
    print("cleanup_failed_count=", result.get("failed_count"), sep="")
    print("status_after=", after["status"] if after else None, sep="")
    print("error_after=", after.get("error") if after else None, sep="")
    print("new_paid_submit_started=False")

    delete_task(task_id)
    print("test_task_deleted=True")

    ok = (
        before
        and before["status"] == "processing"
        and after
        and after["status"] == "failed"
        and "without request_id" in (after.get("error") or "")
        and result.get("new_paid_submit") is False
    )

    if ok:
        print("RESULT=STALE_PROCESSING_CLEANUP_OK")
        return 0

    print("RESULT=STALE_PROCESSING_CLEANUP_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
