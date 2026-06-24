from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import create_task, get_task, list_tasks
from app.queue_worker import process_next_queued_task_dry_run


def main() -> int:
    print("=== Queue worker dry-run check ===")

    params = {
        "model": "seedance-2.0-fast",
        "prompt": "Worker dry-run smoke test only. No paid generation.",
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
        "mode": "worker_dry_run_no_generation",
    }

    task_id = create_task(
        model="seedance-2.0-fast",
        prompt="Worker dry-run smoke test only. No paid generation.",
        params=params,
        refs=[],
        status="queued",
    )

    print(f"created_task_id={task_id}")

    result = process_next_queued_task_dry_run()

    print(f"worker_processed={result.get('processed')}")
    print(f"worker_task_id={result.get('task_id')}")
    print(f"worker_status={result.get('status')}")
    print(f"worker_mode={result.get('mode')}")
    print(f"worker_run_dir={result.get('run_dir')}")

    task = get_task(task_id)

    print(f"db_task_status={task['status'] if task else None}")
    print(f"db_task_run_dir={task['run_dir'] if task else None}")
    print(f"db_task_elapsed={task['elapsed_total_seconds'] if task else None}")

    recent = list_tasks(limit=5)
    print()
    print("=== Recent tasks ===")
    for item in recent:
        print(
            f"#{item['id']} | {item['status']} | {item['model']} | "
            f"{item['params'].get('duration')}s | {item['prompt'][:70]}"
        )

    if (
        result.get("processed") is True
        and result.get("task_id") == task_id
        and task
        and task["status"] == "completed"
        and task["run_dir"]
    ):
        print("RESULT=QUEUE_WORKER_DRY_RUN_OK")
        return 0

    print("RESULT=QUEUE_WORKER_DRY_RUN_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
