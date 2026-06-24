from pathlib import Path
import json
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db import get_task, update_task_fields, utc_now
from app.queue_worker import _download_file, _extract_output_url
from app.segmind_client import SegmindClient
from app.settings import OUTPUT_DIR


def main() -> int:
    task_id = 10

    print("=== Recover failed task by request_id ===")
    print(f"task_id={task_id}")
    print("new_paid_submit=False")

    task = get_task(task_id)

    if not task:
        print("task_found=False")
        print("RESULT=RECOVERY_TASK_NOT_FOUND")
        return 1

    print("task_found=True")
    print(f"task_status_before={task.get('status')}")
    print(f"task_model={task.get('model')}")

    request_id = task.get("request_id")

    if not request_id:
        print("request_id_found=False")
        print("RESULT=RECOVERY_NO_REQUEST_ID")
        return 1

    print("request_id_found=True")
    print(f"request_id={request_id}")

    run_dir_value = task.get("run_dir")
    if run_dir_value:
        run_dir = Path(run_dir_value)
    else:
        run_dir = Path(OUTPUT_DIR) / "queue_runs" / f"task_{task_id:06d}"

    run_dir.mkdir(parents=True, exist_ok=True)

    client = SegmindClient(model=task.get("model"), timeout=180.0)

    try:
        print()
        print("=== Checking remote status ===")

        status_response = client.get_request_status(request_id)
        status = client.extract_status(status_response)

        (run_dir / "recovery_status_response.json").write_text(
            json.dumps(status_response.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"status_code={status_response.status_code}")
        print(f"remote_status={status}")

        if status_response.status_code == 404:
            print("RESULT=RECOVERY_REMOTE_STATUS_404")
            return 1

        if status == "FAILED":
            print("RESULT=RECOVERY_REMOTE_FAILED")
            return 1

        if status != "COMPLETED":
            print("remote_not_completed_yet=True")
            print("No new generation was started. You can retry recovery later.")
            print("RESULT=RECOVERY_REMOTE_NOT_COMPLETED")
            return 2

        print()
        print("=== Fetching completed result ===")

        result_response = client.get_request_result(request_id)

        (run_dir / "recovery_result_response.json").write_text(
            json.dumps(result_response.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"result_status_code={result_response.status_code}")

        if not result_response.ok:
            print("RESULT=RECOVERY_RESULT_FETCH_FAILED")
            return 1

        video_url = _extract_output_url(result_response.data)

        if not video_url:
            print("video_url_found=False")
            print("RESULT=RECOVERY_NO_VIDEO_URL")
            return 1

        print("video_url_found=True")

        video_path = run_dir / "output.mp4"
        _download_file(video_url, video_path)

        inference_time = None
        if isinstance(result_response.data, dict):
            metrics = result_response.data.get("metrics")
            if isinstance(metrics, dict):
                inference_time = metrics.get("inference_time")

        summary = {
            "task_id": task_id,
            "request_id": request_id,
            "model": task.get("model"),
            "status": "completed_recovered",
            "inference_time": inference_time,
            "video_path": str(video_path),
            "video_size_bytes": video_path.stat().st_size,
            "recovered_at": utc_now(),
        }

        (run_dir / "recovery_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        update_task_fields(
            task_id,
            status="completed",
            completed_at=utc_now(),
            inference_time=inference_time,
            output_path=str(video_path),
            error=None,
        )

        print()
        print("=== Recovery completed ===")
        print(f"output_path={video_path}")
        print(f"output_size_bytes={video_path.stat().st_size}")
        print(f"inference_time={inference_time}")
        print("task_status_after=completed")
        print("RESULT=RECOVERY_COMPLETED_OK")
        return 0

    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
        print()
        print("=== Recovery failed ===")
        print(f"error={error_text}")

        (run_dir / "recovery_error.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "request_id": request_id,
                    "error": error_text,
                    "failed_at": utc_now(),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print("RESULT=RECOVERY_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
