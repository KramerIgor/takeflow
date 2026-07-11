from __future__ import annotations

from pathlib import Path
import json

from app.db import get_task, update_task_fields, update_task_params, utc_now
from app.queue_worker import _download_file, _extract_output_url, _save_api_last_frame_if_present, _to_windows_path, _write_status_json
from app.segmind_client import SegmindClient, extract_seed_from_response
from app.settings import OUTPUT_DIR


def recover_task_by_existing_request(task_id: int) -> dict:
    task = get_task(task_id)

    if not task:
        return {
            "processed": False,
            "task_id": task_id,
            "status": "not_found",
            "reason": "task_not_found",
            "new_paid_submit": False,
        }

    request_id = task.get("request_id")

    if not request_id:
        return {
            "processed": False,
            "task_id": task_id,
            "status": task.get("status"),
            "reason": "no_request_id",
            "new_paid_submit": False,
        }

    run_dir = Path(task.get("run_dir") or Path(OUTPUT_DIR) / "queue_runs" / f"task_{task_id:06d}")
    run_dir.mkdir(parents=True, exist_ok=True)

    client = SegmindClient(model=task.get("model"), timeout=180.0)

    try:
        status_response = client.get_request_status(request_id)
        remote_status = client.extract_status(status_response)

        (run_dir / "recovery_status_response.json").write_text(
            json.dumps(status_response.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if status_response.status_code == 404:
            reason = "remote_status_404"
        elif remote_status == "FAILED":
            reason = "remote_failed"
        elif remote_status != "COMPLETED":
            reason = f"remote_status_{remote_status}"
        else:
            reason = None

        if reason:
            return {
                "processed": True,
                "task_id": task_id,
                "status": task.get("status"),
                "reason": reason,
                "request_id": request_id,
                "run_dir": str(run_dir),
                "run_dir_windows_path": _to_windows_path(str(run_dir)),
                "new_paid_submit": False,
            }

        result_response = client.get_request_result(request_id)

        (run_dir / "recovery_result_response.json").write_text(
            json.dumps(result_response.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if not result_response.ok:
            return {
                "processed": True,
                "task_id": task_id,
                "status": "failed",
                "reason": f"result_fetch_failed_{result_response.status_code}",
                "request_id": request_id,
                "run_dir": str(run_dir),
                "run_dir_windows_path": _to_windows_path(str(run_dir)),
                "new_paid_submit": False,
            }

        video_url = _extract_output_url(result_response.data)

        if not video_url:
            return {
                "processed": True,
                "task_id": task_id,
                "status": "failed",
                "reason": "no_video_url",
                "request_id": request_id,
                "run_dir": str(run_dir),
                "run_dir_windows_path": _to_windows_path(str(run_dir)),
                "new_paid_submit": False,
            }

        video_path = run_dir / "output.mp4"
        _download_file(video_url, video_path)
        last_frame_info = _save_api_last_frame_if_present(result_response.data, run_dir)

        inference_time = None
        metrics = result_response.data.get("metrics") if isinstance(result_response.data, dict) else None
        if isinstance(metrics, dict):
            inference_time = metrics.get("inference_time")

        params = dict(task.get("params") or {})
        requested_seed = int(params.get("requested_seed", params.get("seed", -1)))
        is_random_seed = bool(params.get("random_seed", requested_seed < 0))
        actual_seed = next(
            (
                value
                for value in (
                    extract_seed_from_response(result_response),
                    extract_seed_from_response(status_response),
                )
                if value is not None
            ),
            None,
        )
        if actual_seed is None and not is_random_seed:
            actual_seed = requested_seed
        params.update(
            {
                "seed": -1 if is_random_seed else requested_seed,
                "requested_seed": -1 if is_random_seed else requested_seed,
                "random_seed": is_random_seed,
                "actual_seed": actual_seed,
            }
        )
        update_task_params(task_id, params)

        summary = {
            "task_id": task_id,
            "request_id": request_id,
            "model": task.get("model"),
            "status": "completed_recovered",
            "inference_time": inference_time,
            "requested_seed": params["requested_seed"],
            "random_seed": is_random_seed,
            "actual_seed": actual_seed,
            "video_path": str(video_path),
            "video_size_bytes": video_path.stat().st_size,
            "recovered_at": utc_now(),
            "new_paid_submit": False,
            **last_frame_info,
        }

        (run_dir / "recovery_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        _write_status_json(run_dir, summary)

        update_task_fields(
            task_id,
            status="completed",
            completed_at=utc_now(),
            inference_time=inference_time,
            output_path=str(video_path),
            error=None,
        )

        return {
            "processed": True,
            "task_id": task_id,
            "status": "completed",
            "mode": "recovered_existing_request",
            "request_id": request_id,
            "run_dir": str(run_dir),
            "run_dir_windows_path": _to_windows_path(str(run_dir)),
            "output_path": str(video_path),
            "output_windows_path": _to_windows_path(str(video_path)),
            "inference_time": inference_time,
            "new_paid_submit": False,
        }

    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"

        recovery_error_status = {
            "task_id": task_id,
            "status": "failed",
            "request_id": request_id,
            "error": error_text,
            "failed_at": utc_now(),
            "new_paid_submit": False,
        }

        (run_dir / "recovery_error.json").write_text(
            json.dumps(recovery_error_status, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        _write_status_json(run_dir, recovery_error_status)

        return {
            "processed": True,
            "task_id": task_id,
            "status": "failed",
            "reason": "recovery_exception",
            "request_id": request_id,
            "run_dir": str(run_dir),
            "run_dir_windows_path": _to_windows_path(str(run_dir)),
            "error": error_text,
            "new_paid_submit": False,
        }
