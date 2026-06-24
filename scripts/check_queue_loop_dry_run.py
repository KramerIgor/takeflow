from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import create_task, delete_task, get_task, list_tasks
from app.queue_worker import process_queue_loop


def queued_tasks_count() -> int:
    return len([task for task in list_tasks(limit=1000) if task["status"] == "queued"])


def main() -> int:
    print("=== Queue loop dry-run check ===")

    queued_before = queued_tasks_count()
    print("queued_before=", queued_before, sep="")

    if queued_before != 0:
        print("RESULT=SKIPPED_BECAUSE_QUEUED_TASKS_EXIST")
        return 2

    created_ids = []

    for index in range(1, 3):
        params = {
            "model": "seedance-2.0-fast",
            "prompt": f"Queue loop dry-run smoke test #{index}. No paid generation.",
            "reference_images": [],
            "reference_videos": [],
            "reference_audios": [],
            "duration": 4,
            "resolution": "480p",
            "aspect_ratio": "16:9",
            "generate_audio": False,
            "seed": -1,
            "return_last_frame": False,
            "skip_moderation": False,
            "mode": "queue_loop_dry_run_no_generation",
        }

        task_id = create_task(
            model="seedance-2.0-fast",
            prompt=f"Queue loop dry-run smoke test #{index}. No paid generation.",
            params=params,
            refs=[],
            status="queued",
        )
        created_ids.append(task_id)

    print("created_task_ids=", created_ids, sep="")

    result = process_queue_loop(dry_run=True, max_tasks=2, stop_on_failure=True)

    print("loop_dry_run=", result.get("dry_run"), sep="")
    print("loop_processed_count=", result.get("processed_count"), sep="")
    print("loop_completed_count=", result.get("completed_count"), sep="")
    print("loop_failed_count=", result.get("failed_count"), sep="")

    statuses = []
    for task_id in created_ids:
        task = get_task(task_id)
        statuses.append(task["status"] if task else None)

    print("created_task_statuses=", statuses, sep="")

    for task_id in created_ids:
        delete_task(task_id)

    print("smoke_tasks_deleted=True")
    print("queued_after_cleanup=", queued_tasks_count(), sep="")

    if (
        result.get("dry_run") is True
        and result.get("processed_count") == 2
        and result.get("completed_count") == 2
        and statuses == ["completed", "completed"]
        and queued_tasks_count() == 0
    ):
        print("RESULT=QUEUE_LOOP_DRY_RUN_OK")
        return 0

    print("RESULT=QUEUE_LOOP_DRY_RUN_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
