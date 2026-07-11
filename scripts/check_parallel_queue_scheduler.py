from __future__ import annotations

from pathlib import Path
import os
import shutil
import sys
import tempfile
import threading
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

TEST_ROOT = Path(tempfile.mkdtemp(prefix="takeflow_parallel_queue_"))
PROJECT_DIR = TEST_ROOT / "outputs" / "MyFirstProject"
os.environ["TAKEFLOW_DATA_DIR"] = str(TEST_ROOT / "data")
os.environ["OUTPUT_ROOT"] = str(TEST_ROOT / "outputs")
os.environ["OUTPUT_DIR"] = str(PROJECT_DIR)

from app.db import create_task, get_task, init_db, update_task_fields
import app.queue_worker as worker


def create_queue_task(prompt: str, *, parent_task_id: int | None = None) -> int:
    params = {
        "project_name": "MyFirstProject",
        "project_dir": str(PROJECT_DIR),
        "model": "seedance-2.0-fast",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "mode": "parallel_scheduler_test_no_generation",
    }
    if parent_task_id is not None:
        params.update(
            {
                "parent_task_id": parent_task_id,
                "continuation_mode": "last_frame_as_reference",
            }
        )
    return create_task(model="seedance-2.0-fast", prompt=prompt, params=params, refs=[], status="queued")


def main() -> int:
    print("=== Parallel queue scheduler check ===")
    init_db()
    parent_id = create_queue_task("Parent task")
    independent_id = create_queue_task("Independent task")
    child_id = create_queue_task("Continuation child", parent_task_id=parent_id)

    lock = threading.Lock()
    active = 0
    peak_active = 0
    started: list[int] = []
    finished: list[int] = []
    claimed_statuses: list[str | None] = []
    original = worker.process_queued_task_real_by_id

    def fake_process(task_id: int, allow_processing: bool = False) -> dict:
        nonlocal active, peak_active
        with lock:
            active += 1
            peak_active = max(peak_active, active)
            started.append(task_id)
            claimed_statuses.append((get_task(task_id) or {}).get("status"))
        update_task_fields(task_id, status="processing")
        time.sleep(0.08)
        update_task_fields(task_id, status="completed")
        with lock:
            active -= 1
            finished.append(task_id)
        return {"processed": True, "task_id": task_id, "status": "completed", "new_paid_submit_started": False}

    worker.process_queued_task_real_by_id = fake_process
    statuses: list[str | None] = []
    guard_status = None
    guard_result: dict = {}
    try:
        result = worker.process_queue_loop(
            dry_run=False,
            max_tasks=3,
            max_concurrency=2,
            stop_on_failure=True,
            project_name="MyFirstProject",
            project_dir=str(PROJECT_DIR),
        )
        statuses = [(get_task(task_id) or {}).get("status") for task_id in (parent_id, independent_id, child_id)]
        guard_id = create_queue_task("Worker exception guard")

        def exploding_process(task_id: int, allow_processing: bool = False) -> dict:
            raise RuntimeError("synthetic worker crash before normal error handling")

        worker.process_queued_task_real_by_id = exploding_process
        guard_result = worker.process_queue_loop(
            dry_run=False,
            max_tasks=1,
            max_concurrency=2,
            stop_on_failure=True,
            project_name="MyFirstProject",
            project_dir=str(PROJECT_DIR),
        )
        guard_status = (get_task(guard_id) or {}).get("status")
    finally:
        worker.process_queued_task_real_by_id = original
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    first_wave = set(started[:2])
    child_started_after_parent_finished = child_id in started and started.index(child_id) >= 2 and parent_id in finished
    all_completed = statuses == ["completed", "completed", "completed"]

    print("first_wave_has_independent_tasks=", first_wave == {parent_id, independent_id}, sep="")
    print("peak_parallel_jobs=", peak_active, sep="")
    print("claimed_before_worker=", claimed_statuses, sep="")
    print("child_started_after_parent_wave=", child_started_after_parent_finished, sep="")
    print("processed_count=", result.get("processed_count"), sep="")
    print("completed_count=", result.get("completed_count"), sep="")
    print("task_statuses=", statuses, sep="")
    print("worker_exception_becomes_failed=", guard_status == "failed", sep="")
    print("new_paid_submit_started=False")

    ok = (
        first_wave == {parent_id, independent_id}
        and peak_active == 2
        and claimed_statuses == ["processing", "processing", "processing"]
        and child_started_after_parent_finished
        and result.get("processed_count") == 3
        and result.get("completed_count") == 3
        and result.get("max_concurrency") == 2
        and all_completed
        and guard_status == "failed"
        and guard_result.get("failed_count") == 1
    )
    print("RESULT=PARALLEL_QUEUE_SCHEDULER_OK" if ok else "RESULT=PARALLEL_QUEUE_SCHEDULER_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
