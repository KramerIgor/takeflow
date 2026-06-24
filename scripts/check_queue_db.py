from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import DB_PATH, create_task, delete_task, get_next_queued_task, get_task, init_db, list_tasks, update_task_status


def main() -> int:
    print("=== SQLite queue DB check ===")

    init_db()
    print(f"db_path={DB_PATH}")
    print(f"db_exists={DB_PATH.exists()}")

    params = {
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "generate_audio": False,
        "return_last_frame": False,
        "seed": -1,
        "mode": "db_smoke_test_no_generation",
    }

    refs = []

    task_id = create_task(
        model="seedance-2.0-fast",
        prompt="DB smoke test only. No generation.",
        params=params,
        refs=refs,
        status="queued",
    )

    print(f"created_task_id={task_id}")

    task = get_task(task_id)
    print(f"loaded_task_status={task['status'] if task else None}")
    print(f"loaded_task_model={task['model'] if task else None}")

    next_task = get_next_queued_task()
    print(f"next_queued_task_id={next_task['id'] if next_task else None}")

    update_task_status(task_id, "paused", error=None)

    updated = get_task(task_id)
    print(f"updated_task_status={updated['status'] if updated else None}")

    delete_task(task_id)

    deleted = get_task(task_id)
    print(f"deleted_task_is_none={deleted is None}")

    recent_count = len(list_tasks(limit=10))
    print(f"recent_tasks_count={recent_count}")

    if DB_PATH.exists() and deleted is None:
        print("RESULT=QUEUE_DB_OK")
        return 0

    print("RESULT=QUEUE_DB_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
