from pathlib import Path
from collections import Counter
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import list_tasks


def contains(path: str, needle: str) -> bool:
    return needle in Path(path).read_text(encoding="utf-8")


def main() -> int:
    print("=== Stage 6 storage contract check ===")

    checks = {
        "storage_helper_exists": Path("app/storage.py").exists(),
        "queue_worker_uses_take_dirs": contains("app/queue_worker.py", "allocate_inbox_take_dir"),
        "queue_worker_writes_status_json": contains("app/queue_worker.py", "_write_status_json"),
        "recovery_writes_status_json": contains("app/task_recovery.py", "_write_status_json"),
        "gui_shows_result_folder": contains("app/templates/index.html", "Result folder:"),
        "gui_open_path_uses_run_dir_or_output": contains("app/templates/index.html", "task.output_path or task.run_dir"),
        "env_documents_active_project": contains(".env.example", "Active project output folder"),
        "readme_documents_output_model": contains("README.md", "Output storage model"),
    }

    worker_text = Path("app/queue_worker.py").read_text(encoding="utf-8")
    checks["dry_run_take_dir"] = "run_dir = allocate_inbox_take_dir()" in worker_text
    checks["real_run_take_dir"] = worker_text.count("run_dir = allocate_inbox_take_dir()") >= 2

    required_files = [
        "output.mp4",
        "prompt.txt",
        "params.json",
        "refs.json",
        "status.json",
        "errors.log if failed",
        "last_frame.png if return_last_frame later",
    ]

    for name, ok in checks.items():
        print(f"{name}={ok}")

    print()
    print("=== Required result folder files ===")
    for item in required_files:
        print(f"- {item}")

    print()
    print("=== Current queue summary ===")
    tasks = list_tasks(limit=1000)
    counts = Counter(task["status"] for task in tasks)
    print(f"total_tasks={len(tasks)}")
    for status in sorted(counts):
        print(f"{status}={counts[status]}")

    attention = [
        task for task in tasks
        if task["status"] in ["queued", "processing", "recoverable", "failed"]
    ]

    print()
    print("tasks_needing_attention=", len(attention), sep="")
    for task in attention:
        print(
            f"#{task['id']} | {task['status']} | "
            f"request_id={'yes' if task.get('request_id') else 'no'} | "
            f"output={'yes' if task.get('output_path') else 'no'}"
        )

    print()
    print("new_paid_submit_started=False")

    if all(checks.values()):
        print("RESULT=STAGE6_STORAGE_CONTRACT_OK")
        return 0

    print("RESULT=STAGE6_STORAGE_CONTRACT_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
