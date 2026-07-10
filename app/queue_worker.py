from __future__ import annotations

from pathlib import Path
import json
import shutil
import time
from typing import Any

import httpx

from app.db import get_next_queued_task, get_task, update_task_fields, utc_now
from app.segmind_client import SegmindClient
from app.settings import OUTPUT_DIR
from app.storage import allocate_inbox_take_dir, allocate_take_paths
from app.costing import build_cost_info
from app.last_frame import extract_last_frame_candidate


def _take_paths_for_task(params: dict) -> dict:
    project_name = None
    episode_name = None
    scene_name = None

    if isinstance(params, dict):
        project_name = params.get("project_name") or params.get("active_project_name")
        episode_name = params.get("episode_name") or params.get("episode")
        scene_name = params.get("scene_name") or params.get("scene")

    return allocate_take_paths(
        project_name=project_name,
        episode_name=episode_name,
        scene_name=scene_name,
    )


def _allocate_run_dir_for_task(params: dict) -> Path:
    return Path(_take_paths_for_task(params)["run_dir"])


def _run_dir_for_task(params: dict) -> Path:
    run_dir = params.get("run_dir") if isinstance(params, dict) else None
    if run_dir:
        return Path(run_dir)
    return _allocate_run_dir_for_task(params)


def _shared_last_frame_path_for_run_dir(run_dir: Path) -> Path:
    project_dir = run_dir.parent.parent
    last_frames_dir = project_dir / "last_frames"
    last_frames_dir.mkdir(parents=True, exist_ok=True)
    return last_frames_dir / f"{run_dir.name}_last_frame.png"


def _save_api_last_frame_if_present(result_data: dict, run_dir: Path) -> dict:
    candidate = extract_last_frame_candidate(result_data)

    if not candidate:
        return {
            "last_frame_found": False,
            "last_frame_source": None,
            "last_frame_url": None,
            "last_frame_path": None,
            "last_frame_shared_path": None,
            "last_frame_shared_windows_path": None,
            "last_frame_key_path": None,
            "last_frame_candidate_score": None,
            "last_frame_candidate_reason": None,
        }

    shared_last_frame_path = _shared_last_frame_path_for_run_dir(run_dir)
    _download_file(candidate.url, shared_last_frame_path)

    return {
        "last_frame_found": True,
        "last_frame_source": "api",
        "last_frame_url": candidate.url,
        "last_frame_path": str(shared_last_frame_path),
        "last_frame_shared_path": str(shared_last_frame_path),
        "last_frame_shared_windows_path": _to_windows_path(str(shared_last_frame_path)),
        "last_frame_key_path": candidate.key_path,
        "last_frame_candidate_score": candidate.score,
        "last_frame_candidate_reason": candidate.reason,
    }


def _final_video_path_for_run_dir(run_dir: Path) -> Path:
    project_dir = run_dir.parent.parent
    videos_dir = project_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    return videos_dir / f"{run_dir.name}.mp4"


def _final_video_path_for_task(params: dict, run_dir: Path) -> Path:
    video_path = params.get("video_path") if isinstance(params, dict) else None
    if video_path:
        path = Path(video_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return _final_video_path_for_run_dir(run_dir)


def _is_last_frame_reference_continuation(params: dict) -> bool:
    if not isinstance(params, dict):
        return False

    return (
        params.get("continuation_mode") == "last_frame_as_reference"
        and params.get("parent_task_id") is not None
    )


def _resolve_task_last_frame_path(task: dict) -> Path | None:
    candidates = []

    run_dir = task.get("run_dir")
    if run_dir:
        try:
            summary_path = Path(run_dir) / "summary.json"
            if summary_path.exists():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                for key in ("last_frame_shared_path", "last_frame_path"):
                    value = summary.get(key)
                    if value:
                        candidates.append(Path(value))
        except Exception:
            pass

    run_dir = task.get("run_dir")
    if run_dir:
        candidates.append(Path(run_dir) / "last_frame.png")

    output_path = task.get("output_path")
    if output_path:
        output = Path(output_path)
        if output.parent.name == "videos":
            candidates.append(output.parent.parent / "runs" / output.stem / "last_frame.png")

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            continue

        if resolved.exists() and resolved.is_file():
            return resolved

    return None


def _append_parent_last_frame_ref(refs: list[dict], parent_last_frame_path: Path, parent_task_id: int, params: dict) -> list[dict]:
    resolved_path = str(parent_last_frame_path)
    prepared_refs = [dict(item) for item in refs]

    for item in prepared_refs:
        local_path = item.get("local_path")
        same_file = False
        if local_path:
            try:
                same_file = Path(local_path).samefile(parent_last_frame_path)
            except (OSError, ValueError):
                try:
                    same_file = os.path.normcase(str(Path(local_path).resolve())) == os.path.normcase(resolved_path)
                except (OSError, ValueError):
                    same_file = False

        if same_file:
            item.setdefault("role", "parent_last_frame_reference")
            item.setdefault("source", "queue_chain")
            item.setdefault("parent_task_id", parent_task_id)
            item.setdefault("parent_take_stem", params.get("parent_take_stem"))
            return prepared_refs

    prepared_refs.append(
        {
            "role": "parent_last_frame_reference",
            "local_path": resolved_path,
            "source": "queue_chain",
            "parent_task_id": parent_task_id,
            "parent_take_stem": params.get("parent_take_stem"),
        }
    )

    return prepared_refs


def _prepare_continuation_task_refs(task: dict) -> dict:
    params = task.get("params") or {}

    if not _is_last_frame_reference_continuation(params):
        return {
            "ready": True,
            "refs": task.get("refs") or [],
        }

    task_id = int(task["id"])
    parent_task_id = int(params["parent_task_id"])
    parent_task = get_task(parent_task_id)

    if not parent_task:
        error = f"Parent task #{parent_task_id} was not found for continuation task #{task_id}."
        update_task_fields(
            task_id,
            status="failed",
            completed_at=utc_now(),
            error=error,
        )
        return {
            "ready": False,
            "status": "failed",
            "reason": "parent_task_not_found",
            "task_id": task_id,
            "parent_task_id": parent_task_id,
            "error": error,
        }

    parent_status = parent_task.get("status")
    if parent_status != "completed":
        return {
            "ready": False,
            "processed": False,
            "reason": "waiting_for_parent_task",
            "task_id": task_id,
            "parent_task_id": parent_task_id,
            "parent_status": parent_status,
        }

    parent_last_frame_path = _resolve_task_last_frame_path(parent_task)
    if not parent_last_frame_path:
        error = (
            f"Parent task #{parent_task_id} is completed, but last_frame.png was not found. "
            "Continuation task was not submitted."
        )
        update_task_fields(
            task_id,
            status="failed",
            completed_at=utc_now(),
            error=error,
        )
        return {
            "ready": False,
            "status": "failed",
            "reason": "parent_last_frame_missing",
            "task_id": task_id,
            "parent_task_id": parent_task_id,
            "error": error,
        }

    return {
        "ready": True,
        "refs": _append_parent_last_frame_ref(
            task.get("refs") or [],
            parent_last_frame_path,
            parent_task_id,
            params,
        ),
        "parent_task_id": parent_task_id,
        "parent_last_frame_path": str(parent_last_frame_path),
    }


def _write_status_json(run_dir: Path, status_data: dict) -> None:
    (run_dir / "status.json").write_text(
        json.dumps(status_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _log(message: str) -> None:
    line = f"[QUEUE] {message}"

    try:
        with Path("/tmp/seedance_gui_queue_worker.log").open("a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")
    except Exception:
        pass

    try:
        print(line, flush=True)
    except (BrokenPipeError, OSError):
        pass


def _is_retryable_pre_submit_error(error_text: str) -> bool:
    retryable_markers = (
        "Reference upload timed out before Segmind submit",
        "Reference upload failed with status 5",
    )
    return any(marker in error_text for marker in retryable_markers)


def _to_windows_path(path_value: str | None) -> str | None:
    if not path_value:
        return None

    path_value = str(path_value)

    if path_value.startswith("/mnt/c/"):
        return "C:\\" + path_value.removeprefix("/mnt/c/").replace("/", "\\")

    if path_value.startswith("/mnt/d/"):
        return "D:\\" + path_value.removeprefix("/mnt/d/").replace("/", "\\")

    return path_value


def _extract_output_url(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None

    candidates: list[str] = []

    for key in ("output", "video", "video_url", "url"):
        value = data.get(key)
        if isinstance(value, str):
            candidates.append(value)

    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if isinstance(item, str):
                candidates.append(item)
            elif isinstance(item, dict):
                for key in ("url", "video_url"):
                    value = item.get(key)
                    if isinstance(value, str):
                        candidates.append(value)

    if isinstance(output, dict):
        for key in ("url", "video_url"):
            value = output.get(key)
            if isinstance(value, str):
                candidates.append(value)

    video = data.get("video")
    if isinstance(video, dict):
        value = video.get("url")
        if isinstance(value, str):
            candidates.append(value)

    for value in candidates:
        if value.startswith("http://") or value.startswith("https://"):
            return value

    return None



def _download_file(url: str, path: Path) -> None:
    _log(f"downloading output to {path}")

    with httpx.stream("GET", url, timeout=300.0) as response:
        response.raise_for_status()
        with path.open("wb") as f:
            for chunk in response.iter_bytes():
                if chunk:
                    f.write(chunk)

    _log(f"download completed: {path.stat().st_size} bytes")


def _get_next_queued_task_for_project(project_name: str | None, project_dir: str | None) -> dict | None:
    if project_name or project_dir:
        return get_next_queued_task(project_name=project_name, project_dir=project_dir)
    return get_next_queued_task()


def process_next_queued_task_dry_run(*, project_name: str | None = None, project_dir: str | None = None) -> dict:
    task = _get_next_queued_task_for_project(project_name, project_dir)

    if task is None:
        _log("dry-run: no queued tasks")
        return {
            "processed": False,
            "reason": "no_queued_tasks",
        }

    task_id = int(task["id"])
    started = time.time()
    started_at = utc_now()

    params = task["params"]
    refs = task["refs"]

    _log(f"dry-run task #{task_id}: start")

    continuation_preflight = _prepare_continuation_task_refs(task)
    if not continuation_preflight.get("ready"):
        reason = continuation_preflight.get("reason")
        _log(f"dry-run task #{task_id}: continuation preflight stop | reason={reason}")
        return {
            "processed": continuation_preflight.get("processed", True),
            "task_id": task_id,
            "status": continuation_preflight.get("status"),
            "mode": "dry_run_no_paid_generation",
            "reason": reason,
            "parent_task_id": continuation_preflight.get("parent_task_id"),
            "parent_status": continuation_preflight.get("parent_status"),
            "error": continuation_preflight.get("error"),
        }

    refs = continuation_preflight.get("refs") or refs

    run_dir = _run_dir_for_task(params)
    run_dir.mkdir(parents=True, exist_ok=True)
    expected_video_path = _final_video_path_for_run_dir(run_dir)

    update_task_fields(
        task_id,
        status="processing",
        started_at=started_at,
        run_dir=str(run_dir),
        error=None,
    )

    (run_dir / "task.json").write_text(
        json.dumps(task, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "prompt.txt").write_text(task["prompt"], encoding="utf-8")
    (run_dir / "params.json").write_text(
        json.dumps(params, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "refs.json").write_text(
        json.dumps(refs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    time.sleep(1)

    elapsed = int(time.time() - started)
    completed_at = utc_now()

    summary = {
        "task_id": task_id,
        "status": "completed",
        "mode": "dry_run_no_paid_generation",
        "elapsed_total_seconds": elapsed,
        "run_dir": str(run_dir),
        "expected_video_path": str(expected_video_path),
    }

    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    _write_status_json(run_dir, summary)

    update_task_fields(
        task_id,
        status="completed",
        completed_at=completed_at,
        elapsed_total_seconds=elapsed,
        inference_time=None,
        output_path=None,
        error=None,
    )

    _log(f"dry-run task #{task_id}: completed in {elapsed}s")

    return {
        "processed": True,
        "task_id": task_id,
        "status": "completed",
        "mode": "dry_run_no_paid_generation",
        "run_dir": str(run_dir),
        "run_dir_windows_path": _to_windows_path(str(run_dir)),
        "elapsed_total_seconds": elapsed,
    }


def process_queued_task_real_by_id(task_id: int) -> dict:
    task = get_task(task_id)

    if task is None:
        _log(f"real worker: task #{task_id} was not found")
        return {
            "processed": False,
            "reason": "task_not_found",
            "task_id": task_id,
        }

    if task.get("status") != "queued":
        _log(f"real worker: task #{task_id} is not queued | status={task.get('status')}")
        return {
            "processed": False,
            "reason": "task_not_queued",
            "task_id": task_id,
            "status": task.get("status"),
        }

    return _process_queued_task_real(task)


def process_next_queued_task_real(*, project_name: str | None = None, project_dir: str | None = None) -> dict:
    task = _get_next_queued_task_for_project(project_name, project_dir)

    if task is None:
        _log("real worker: no queued tasks")
        return {
            "processed": False,
            "reason": "no_queued_tasks",
        }

    return _process_queued_task_real(task)


def _process_queued_task_real(task: dict) -> dict:
    task_id = int(task["id"])
    params = task["params"]
    refs = task["refs"]

    started = time.time()
    started_at = utc_now()

    model = task["model"]

    continuation_preflight = _prepare_continuation_task_refs(task)
    if not continuation_preflight.get("ready"):
        reason = continuation_preflight.get("reason")
        _log(f"task #{task_id}: continuation preflight stop | reason={reason}")
        return {
            "processed": continuation_preflight.get("processed", True),
            "task_id": task_id,
            "status": continuation_preflight.get("status"),
            "mode": "continuation_preflight_no_paid_generation",
            "reason": reason,
            "parent_task_id": continuation_preflight.get("parent_task_id"),
            "parent_status": continuation_preflight.get("parent_status"),
            "error": continuation_preflight.get("error"),
            "new_paid_submit_started": False,
        }

    refs = continuation_preflight.get("refs") or refs
    run_dir = _run_dir_for_task(params)
    run_dir.mkdir(parents=True, exist_ok=True)

    _log(
        f"task #{task_id}: start real generation | "
        f"model={model} duration={params.get('duration')} "
        f"resolution={params.get('resolution')} aspect={params.get('aspect_ratio')}"
    )

    update_task_fields(
        task_id,
        status="processing",
        started_at=started_at,
        run_dir=str(run_dir),
        error=None,
    )

    request_id = None

    try:
        client = SegmindClient(model=model, timeout=600.0)

        refs_for_api = [item for item in refs if item.get("media_type") in (None, "image")]
        stored_reference_videos = [item.get("local_path") for item in refs if item.get("media_type") == "video" and item.get("local_path")]
        stored_reference_audios = [item.get("local_path") for item in refs if item.get("media_type") == "audio" and item.get("local_path")]
        uploaded_reference_urls: list[str] = []
        refs_for_save = []

        if refs_for_api:
            _log(f"task #{task_id}: uploading {len(refs_for_api)} reference image(s)")
        else:
            _log(f"task #{task_id}: no reference images")

        for index, item in enumerate(refs_for_api, start=1):
            local_path = item.get("local_path")
            if not local_path:
                continue

            _log(f"task #{task_id}: upload reference {index}/{len(refs_for_api)}")

            try:
                upload_response = client.upload_asset(local_path)
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    "Reference upload timed out before Segmind submit. "
                    "No Segmind request was created; retry or use smaller reference files."
                ) from exc

            safe_role = str(item.get("role", "reference")).replace(" ", "_")
            (run_dir / f"upload_response_{safe_role}.json").write_text(
                json.dumps(upload_response.data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            if not upload_response.ok:
                raise RuntimeError(f"Reference upload failed with status {upload_response.status_code}")

            uploaded_url = client.extract_uploaded_asset_url(upload_response)
            if not uploaded_url:
                raise RuntimeError("Reference upload succeeded, but no URL was found in response.")

            saved_item = dict(item)
            saved_item["uploaded_url_present"] = True
            refs_for_save.append(saved_item)
            uploaded_reference_urls.append(uploaded_url)

        payload = client.build_seedance_payload(
            prompt=task["prompt"],
            reference_images=uploaded_reference_urls,
            reference_videos=[],
            reference_audios=[],
            duration=int(params.get("duration", 4)),
            resolution=str(params.get("resolution", "480p")),
            aspect_ratio=str(params.get("aspect_ratio", "16:9")),
            generate_audio=bool(params.get("generate_audio", False)),
            seed=int(params.get("seed", -1)),
            return_last_frame=bool(params.get("return_last_frame", False)),
        )

        params_for_save = dict(payload)
        params_for_save["model"] = model
        params_for_save["stored_reference_videos"] = stored_reference_videos
        params_for_save["stored_reference_audios"] = stored_reference_audios
        params_for_save["video_audio_submission_status"] = "stored_only_not_sent_to_api" if (stored_reference_videos or stored_reference_audios) else "not_applicable"
        params_for_save["reference_images"] = [
            {
                "local_path": item.get("local_path"),
                "uploaded_url_present": item.get("uploaded_url_present", False),
            }
            for item in refs_for_save
        ]

        (run_dir / "task.json").write_text(
            json.dumps(task, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "prompt.txt").write_text(task["prompt"], encoding="utf-8")
        (run_dir / "params.json").write_text(
            json.dumps(params_for_save, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (run_dir / "refs.json").write_text(
            json.dumps(refs_for_save, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        _log(f"task #{task_id}: submitting to Segmind")
        submit_response = client.submit_seedance_async(payload)

        (run_dir / "submit_response.json").write_text(
            json.dumps(submit_response.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if not submit_response.ok:
            raise RuntimeError(f"Submit failed with status {submit_response.status_code}: {submit_response.text_preview}")

        request_id = client.extract_request_id(submit_response)
        if not request_id:
            raise RuntimeError("Submit succeeded, but request_id was not found.")

        _log(f"task #{task_id}: submitted | request_id={request_id}")
        update_task_fields(task_id, request_id=request_id)

        transient_404_count = 0
        transient_network_error_count = 0
        max_transient_network_errors = 30

        while True:
            elapsed_now = int(time.time() - started)

            try:
                status_response = client.get_request_status(request_id)
                status = client.extract_status(status_response)
                transient_network_error_count = 0
            except Exception as exc:
                transient_network_error_count += 1
                error_text = f"{type(exc).__name__}: {exc}"

                _log(
                    f"task #{task_id}: polling network error "
                    f"{transient_network_error_count}/{max_transient_network_errors} | "
                    f"elapsed={elapsed_now}s | will retry automatically | {error_text}"
                )

                (run_dir / "last_polling_network_error.json").write_text(
                    json.dumps(
                        {
                            "task_id": task_id,
                            "request_id": request_id,
                            "elapsed_seconds": elapsed_now,
                            "error_count": transient_network_error_count,
                            "max_error_count": max_transient_network_errors,
                            "behavior": "automatic_retry_before_recoverable",
                            "error": error_text,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                if transient_network_error_count <= max_transient_network_errors:
                    time.sleep(10)
                    continue

                raise RuntimeError(
                    "Polling did not recover automatically after repeated network errors. Task will become recoverable: "
                    f"{error_text}"
                )

            (run_dir / "last_status.json").write_text(
                json.dumps(status_response.data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            _log(
                f"task #{task_id}: polling | "
                f"elapsed={elapsed_now}s status_code={status_response.status_code} status={status}"
            )

            if status_response.status_code == 404:
                transient_404_count += 1
                _log(f"task #{task_id}: transient 404 #{transient_404_count}, retrying")
                if transient_404_count <= 3:
                    time.sleep(10)
                    continue
                raise RuntimeError("Status endpoint returned repeated 404 responses.")

            if status == "COMPLETED":
                break

            if status == "FAILED":
                raise RuntimeError(f"Generation failed: {status_response.text_preview}")

            if status_response.status_code == 401:
                raise RuntimeError("Segmind authorization failed during polling.")

            time.sleep(10)

        _log(f"task #{task_id}: fetching result")
        result_response = client.get_request_result(request_id)

        (run_dir / "result_response.json").write_text(
            json.dumps(result_response.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if not result_response.ok:
            raise RuntimeError(f"Result fetch failed with status {result_response.status_code}: {result_response.text_preview}")

        video_url = _extract_output_url(result_response.data)
        if not video_url:
            raise RuntimeError("No video URL found in result response.")

        video_path = _final_video_path_for_task(params, run_dir)
        _download_file(video_url, video_path)

        last_frame_info = _save_api_last_frame_if_present(result_response.data, run_dir)

        elapsed_total_seconds = int(time.time() - started)
        completed_at = utc_now()
        inference_time = None

        if isinstance(result_response.data, dict):
            metrics = result_response.data.get("metrics")
            if isinstance(metrics, dict):
                inference_time = metrics.get("inference_time")

        summary = {
            "task_id": task_id,
            "request_id": request_id,
            "model": model,
            "status": "completed",
            "elapsed_total_seconds": elapsed_total_seconds,
            "inference_time": inference_time,
            "video_path": str(video_path),
            "cost_info": build_cost_info(result_response.data, model=model, duration=params.get("duration"), resolution=params.get("resolution"), aspect_ratio=params.get("aspect_ratio"), refs=refs),
            "technical_output_path": None,
            "video_size_bytes": video_path.stat().st_size,
            **last_frame_info,
        }

        (run_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        _write_status_json(run_dir, summary)

        update_task_fields(
            task_id,
            status="completed",
            completed_at=completed_at,
            elapsed_total_seconds=elapsed_total_seconds,
            inference_time=inference_time,
            output_path=str(video_path),
            error=None,
        )

        _log(
            f"task #{task_id}: completed | "
            f"elapsed={elapsed_total_seconds}s inference={inference_time}s "
            f"output={video_path}"
        )

        return {
            "processed": True,
            "task_id": task_id,
            "status": "completed",
            "mode": "real_paid_generation",
            "run_dir": str(run_dir),
            "run_dir_windows_path": _to_windows_path(str(run_dir)),
            "output_path": str(video_path),
            "output_windows_path": _to_windows_path(str(video_path)),
            "elapsed_total_seconds": elapsed_total_seconds,
            "inference_time": inference_time,
        }

    except Exception as exc:
        elapsed_total_seconds = int(time.time() - started)
        completed_at = utc_now()

        error_text = f"{type(exc).__name__}: {exc}"

        _log(f"task #{task_id}: failed | elapsed={elapsed_total_seconds}s error={error_text}")

        (run_dir / "errors.log").write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "status": "failed",
                    "error": error_text,
                    "elapsed_total_seconds": elapsed_total_seconds,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        retryable_pre_submit = request_id is None and _is_retryable_pre_submit_error(error_text)
        status_to_set = "recoverable" if request_id else ("queued" if retryable_pre_submit else "failed")
        result_status = "failed" if retryable_pre_submit else status_to_set
        result_reason = "retryable_pre_submit_failure" if retryable_pre_submit else None

        if status_to_set == "recoverable":
            _log(
                f"task #{task_id}: marked as recoverable because request_id exists | "
                f"request_id={request_id}"
            )
        elif retryable_pre_submit:
            _log(
                f"task #{task_id}: left queued for retry because failure happened before Segmind submit"
            )

        update_fields = {
            "status": status_to_set,
            "completed_at": None if retryable_pre_submit else completed_at,
            "started_at": None if retryable_pre_submit else started_at,
            "elapsed_total_seconds": elapsed_total_seconds,
            "error": error_text,
        }
        update_task_fields(task_id, **update_fields)

        result = {
            "processed": True,
            "task_id": task_id,
            "status": result_status,
            "mode": "real_paid_generation",
            "request_id": request_id,
            "run_dir": str(run_dir),
            "run_dir_windows_path": _to_windows_path(str(run_dir)),
            "error": error_text,
            "elapsed_total_seconds": elapsed_total_seconds,
        }
        if result_reason:
            result["reason"] = result_reason
            result["db_status"] = status_to_set
        return result


def process_queue_loop(
    *,
    dry_run: bool,
    max_tasks: int = 1,
    stop_on_failure: bool = True,
    project_name: str | None = None,
    project_dir: str | None = None,
) -> dict:
    if max_tasks < 1:
        max_tasks = 1

    _log(
        f"queue loop start | dry_run={dry_run} "
        f"max_tasks={max_tasks} stop_on_failure={stop_on_failure}"
    )

    results = []
    completed = 0
    failed = 0

    for index in range(1, max_tasks + 1):
        _log(f"queue loop item {index}/{max_tasks}: checking next queued task")

        if dry_run:
            result = process_next_queued_task_dry_run(project_name=project_name, project_dir=project_dir)
        else:
            result = process_next_queued_task_real(project_name=project_name, project_dir=project_dir)

        if result.get("processed") is False:
            _log(f"queue loop item {index}/{max_tasks}: stop | reason={result.get('reason')}")
            results.append(result)
            break

        results.append(result)

        if result.get("status") == "completed":
            completed += 1
        elif result.get("status") == "failed":
            failed += 1
            if stop_on_failure:
                _log(f"queue loop item {index}/{max_tasks}: stop on failure")
                break

    processed_count = len([item for item in results if item.get("processed") is True])
    stopped_reason = results[-1].get("reason") if results and results[-1].get("processed") is False else None

    _log(
        f"queue loop finished | processed={processed_count} "
        f"completed={completed} failed={failed} stopped_reason={stopped_reason}"
    )

    return {
        "dry_run": dry_run,
        "max_tasks": max_tasks,
        "processed_count": processed_count,
        "completed_count": completed,
        "failed_count": failed,
        "stopped_reason": stopped_reason,
        "results": results,
    }
