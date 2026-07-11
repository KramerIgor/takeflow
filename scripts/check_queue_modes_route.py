from pathlib import Path
import os
import shutil
import sys
import tempfile
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
TEST_ROOT = Path(tempfile.mkdtemp(prefix="takeflow_queue_modes_route_"))
os.environ["TAKEFLOW_DATA_DIR"] = str(TEST_ROOT / "data")
os.environ["OUTPUT_ROOT"] = str(TEST_ROOT / "outputs")
os.environ["OUTPUT_DIR"] = str(TEST_ROOT / "outputs" / "MyFirstProject")

from fastapi.testclient import TestClient
import app.main as main_module
from app.main import app


def main() -> int:
    print("=== Queue modes route check ===")
    calls: list[dict] = []
    original_process = main_module.process_queue_loop
    original_cleanup = main_module.cleanup_processing_without_request_id
    original_recover = main_module.auto_recover_existing_requests

    def fake_process(**kwargs):
        calls.append(kwargs)
        return {
            "dry_run": False,
            "max_tasks": kwargs["max_tasks"],
            "max_concurrency": kwargs["max_concurrency"],
            "processed_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "stopped_reason": "no_queued_tasks",
            "results": [],
        }

    main_module.process_queue_loop = fake_process
    main_module.cleanup_processing_without_request_id = lambda: {"cleaned": 0}
    main_module.auto_recover_existing_requests = lambda: {"completed_count": 0}
    try:
        client = TestClient(app)
        page = client.get("/")
        response = client.post(
            "/start-queue-loop",
            data={"queue_mode": "parallel", "max_tasks": "50", "max_concurrency": "10"},
            follow_redirects=True,
        )
        for _ in range(50):
            if calls:
                break
            time.sleep(0.02)
    finally:
        main_module.process_queue_loop = original_process
        main_module.cleanup_processing_without_request_id = original_cleanup
        main_module.auto_recover_existing_requests = original_recover
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    checks = {
        "route_status_ok": response.status_code == 200,
        "mode_selector_present": 'name="queue_mode"' in page.text,
        "concurrency_input_present": 'name="max_concurrency"' in page.text,
        "parallel_worker_called": bool(calls),
        "max_tasks_forwarded": bool(calls) and calls[0].get("max_tasks") == 50,
        "max_concurrency_forwarded": bool(calls) and calls[0].get("max_concurrency") == 10,
    }
    for name, value in checks.items():
        print(f"{name}={value}")
    print("new_paid_submit_started=False")
    ok = all(checks.values())
    print("RESULT=QUEUE_MODES_ROUTE_OK" if ok else "RESULT=QUEUE_MODES_ROUTE_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
