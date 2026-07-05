from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import csv
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid

import httpx
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import create_task, delete_task, get_task, init_db, list_tasks, update_task_fields, update_task_payload
from app.queue_worker import process_next_queued_task_real, process_queue_loop, process_queued_task_real_by_id, _save_api_last_frame_if_present
from app.settings import ENV_PATH, OUTPUT_DIR, SEGMIND_API_KEY, SEGMIND_API_BASE, SEGMIND_MODEL
from app.segmind_client import SegmindClient
from app.costing import build_cost_info, cost_label, estimate_seedance_cost_info, extract_cost_info
from app.storage import allocate_take_paths, sanitize_folder_part
from app.task_recovery import recover_task_by_existing_request
from app import projects as projects_module


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
STATIC_DIR = PROJECT_ROOT / "app" / "static"

app = FastAPI(title="Seedance GUI", version="0.1.0")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

init_db()


MODEL_CHOICES = [
    {"id": "seedance-2.0", "label": "Seedance 2.0", "note": "Base model"},
    {"id": "seedance-2.0-fast", "label": "Seedance 2.0 Fast", "note": "Faster / cheaper variant"},
]

DURATIONS = list(range(4, 16))
RESOLUTIONS = ["480p", "720p", "1080p"]
ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"]

BATCH_IMPORT_REQUIRED_COLUMNS = [
    "episode_name",
    "scene_name",
    "prompt",
    "model",
    "duration",
    "resolution",
    "aspect_ratio",
    "seed",
    "generate_audio",
    "reference_paths",
]

REFERENCE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
REFERENCE_VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv"}
REFERENCE_AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
REFERENCE_FILE_SUFFIXES = REFERENCE_IMAGE_SUFFIXES | REFERENCE_VIDEO_SUFFIXES | REFERENCE_AUDIO_SUFFIXES
SINGLE_GENERATION_MODES = {"single_generation_paid", "single_generation_regenerate_paid"}



APP_TITLE = "Seedance"
APP_SUBTITLE = "Local video generation workspace"
BALANCE_CACHE_SECONDS = 60
_segmind_balance_cache: dict[str, object] = {"expires_at": 0.0, "context": None}
QUEUE_LOOP_REFRESH_SECONDS = 15
_queue_loop_state_lock = threading.Lock()
_queue_loop_state: dict[str, object] = {
    "active": False,
    "project_name": None,
    "project_dir": None,
    "max_tasks": None,
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
    "stop_requested": False,
    "paused_count": 0,
}


def env_key_is_set() -> bool:
    return bool(os.getenv("SEGMIND_API_KEY", "") or SEGMIND_API_KEY)


def update_env_values(values: dict[str, str]) -> None:
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = []
    if ENV_PATH.exists():
        existing_lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    remaining = dict(values)
    output_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output_lines.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key in remaining:
            output_lines.append(f"{key}={remaining.pop(key)}")
        else:
            output_lines.append(line)

    if remaining and output_lines and output_lines[-1].strip():
        output_lines.append("")

    for key, value in remaining.items():
        output_lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")



def cost_info_for_generation(summary: dict | None, *, model: str | None, params: dict | None, refs: list[dict] | None) -> dict | None:
    if isinstance(summary, dict):
        saved = summary.get("cost_info")
        if isinstance(saved, dict) and (saved.get("items") or saved.get("amount_usd")):
            return saved

    params = params or {}
    return estimate_seedance_cost_info(
        model=model or params.get("model"),
        duration=params.get("duration"),
        resolution=params.get("resolution"),
        aspect_ratio=params.get("aspect_ratio"),
        refs=refs,
        reference_videos=params.get("reference_videos") or [],
    )


def cost_amount_from_info(cost_info: dict | None) -> float | None:
    if not isinstance(cost_info, dict):
        return None

    for key in ("amount_usd", "cost", "price", "amount"):
        value = cost_info.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
            if match:
                return float(match.group(0))

    for item in cost_info.get("items") or []:
        value = item.get("value") if isinstance(item, dict) else None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
            if match:
                return float(match.group(0))

    return None


def cost_label_from_generation(summary: dict | None, *, model: str | None, params: dict | None, refs: list[dict] | None) -> str | None:
    return cost_label(cost_info_for_generation(summary, model=model, params=params, refs=refs))


def format_queue_cost_total(amount: float | None) -> str | None:
    if amount is None:
        return None
    return f"~${amount:.4f} estimated"


def format_credit_amount(value: object) -> str | None:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None

    return f"${amount:,.4f}"


def segmind_balance_context() -> dict:
    if not env_key_is_set():
        return {
            "segmind_balance_label": "Balance",
            "segmind_balance_value": "Unavailable",
            "segmind_balance_hint": "Set an API key in Projects to check Segmind credits.",
            "segmind_balance_available": False,
        }

    now = time.time()
    cached = _segmind_balance_cache.get("context")
    if cached and now < float(_segmind_balance_cache.get("expires_at") or 0):
        return dict(cached)

    context = {
        "segmind_balance_label": "Balance",
        "segmind_balance_value": "Unavailable",
        "segmind_balance_hint": "Could not read Segmind credits from https://api.segmind.com/v1/get-user-credits.",
        "segmind_balance_available": False,
    }

    try:
        response = SegmindClient(timeout=4.0).get_user_credits()
        data = response.data if isinstance(response.data, dict) else {}
        credits_label = format_credit_amount(data.get("credits"))
        free_credits_label = format_credit_amount(data.get("free-credits"))
        if response.ok and credits_label:
            context = {
                "segmind_balance_label": "Balance",
                "segmind_balance_value": credits_label,
                "segmind_balance_hint": f"Segmind credits: {credits_label}; free credits: {free_credits_label or '$0.0000'}.",
                "segmind_balance_available": True,
            }
        elif response.status_code == 401:
            context["segmind_balance_hint"] = "Segmind rejected the API key while reading credits."
        elif response.status_code:
            context["segmind_balance_hint"] = f"Segmind credits endpoint returned HTTP {response.status_code}."
    except Exception as exc:
        context["segmind_balance_hint"] = f"Segmind credits check failed: {type(exc).__name__}."

    _segmind_balance_cache["context"] = dict(context)
    _segmind_balance_cache["expires_at"] = now + BALANCE_CACHE_SECONDS
    return context


def load_summary_for_run(run_dir: str | None) -> dict:
    if not run_dir:
        return {}
    try:
        summary_path = Path(run_dir) / "summary.json"
        if summary_path.exists():
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        return {}
    return {}


def to_windows_path(path_value: str | None) -> str | None:
    if not path_value:
        return None

    path_value = str(path_value)

    if path_value.startswith("/mnt/c/"):
        return "C:\\" + path_value.removeprefix("/mnt/c/").replace("/", "\\")

    if path_value.startswith("/mnt/d/"):
        return "D:\\" + path_value.removeprefix("/mnt/d/").replace("/", "\\")

    return path_value


def reference_media_type_for_path(path_value: str | Path | None) -> str:
    suffix = Path(str(path_value or "")).suffix.lower()

    if suffix in REFERENCE_IMAGE_SUFFIXES:
        return "image"

    if suffix in REFERENCE_VIDEO_SUFFIXES:
        return "video"

    if suffix in REFERENCE_AUDIO_SUFFIXES:
        return "audio"

    return "unsupported"


def ref_view_for_item(ref: dict) -> dict:
    item = dict(ref or {})
    local_path = item.get("local_path")
    media_type = item.get("media_type") or reference_media_type_for_path(local_path)
    filename = item.get("original_filename") or (Path(local_path).name if local_path else "reference")
    preview_url = None
    exists = False

    if local_path:
        try:
            path = Path(local_path).resolve()
            output_root = projects_module.get_output_root().resolve()
            exists = path.exists() and path.is_file()
            if exists:
                local_path = str(path)
            if exists and media_type in {"image", "video", "audio"} and path.is_relative_to(output_root):
                preview_url = "/safe-media-file?path=" + quote(str(path), safe="")
        except Exception:
            exists = False

    item.update(
        {
            "filename": filename,
            "local_path": local_path,
            "windows_path": to_windows_path(local_path),
            "media_type": media_type,
            "preview_url": preview_url,
            "exists": exists,
            "sent_to_api": media_type == "image",
            "api_warning": None if media_type == "image" else "Stored in history; not sent to API yet",
        }
    )
    return item


def sanitize_reference_filename(filename: str, fallback: str) -> str:
    name = Path(filename or fallback).name
    stem = sanitize_folder_part(Path(name).stem, fallback)
    suffix = Path(name).suffix.lower()
    if suffix not in REFERENCE_FILE_SUFFIXES:
        suffix = ""
    return f"{stem}{suffix}"


def single_generation_default_name() -> str:
    existing_count = 0
    for task in active_project_tasks(limit=10000):
        params = task.get("params") or {}
        if params.get("mode") in SINGLE_GENERATION_MODES:
            existing_count += 1

    date_part = datetime.now().strftime("%d%m%Y")
    return f"generation{existing_count + 1:05d}-{date_part}"


def normalize_single_generation_name(value: str | None) -> str:
    raw = (value or "").strip() or single_generation_default_name()
    return sanitize_folder_part(raw, single_generation_default_name())



def project_context() -> dict:
    output_root = projects_module.get_output_root()

    return {
        "active_project_name": projects_module.get_active_project_name(),
        "output_root": str(output_root),
        "output_root_windows_path": to_windows_path(str(output_root)),
        "projects": projects_module.list_projects(root=output_root),
    }


def active_project_task_filter() -> dict:
    return {
        "project_name": projects_module.get_active_project_name(),
        "project_dir": str(projects_module.get_active_project_dir()),
    }


def active_project_tasks(limit: int = 1000) -> list[dict]:
    return list_tasks(limit=limit, **active_project_task_filter())


def queue_loop_state_snapshot() -> dict:
    with _queue_loop_state_lock:
        return dict(_queue_loop_state)


def queue_loop_state_for_active_project() -> dict:
    state = queue_loop_state_snapshot()
    active_name = projects_module.get_active_project_name()
    is_active_project = state.get("project_name") == active_name

    return {
        **state,
        "is_current_project": is_active_project,
        "show": bool(is_active_project and (state.get("active") or state.get("result") or state.get("error"))),
    }


def queue_loop_is_running() -> bool:
    return bool(queue_loop_state_snapshot().get("active"))


def mark_queue_loop_started(*, project_name: str, project_dir: str, max_tasks: int) -> None:
    with _queue_loop_state_lock:
        _queue_loop_state.update(
            {
                "active": True,
                "project_name": project_name,
                "project_dir": project_dir,
                "max_tasks": max_tasks,
                "started_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "finished_at": None,
                "result": None,
                "error": None,
                "stop_requested": False,
                "paused_count": 0,
            }
        )


def mark_queue_loop_finished(*, result: dict | None = None, error: str | None = None) -> None:
    with _queue_loop_state_lock:
        _queue_loop_state.update(
            {
                "active": False,
                "finished_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "result": result,
                "error": error,
            }
        )


def mark_queue_loop_stop_requested(*, paused_count: int) -> None:
    with _queue_loop_state_lock:
        _queue_loop_state.update(
            {
                "stop_requested": True,
                "paused_count": paused_count,
            }
        )


def pause_active_project_queued_tasks() -> list[int]:
    paused_task_ids: list[int] = []
    for task in active_project_tasks(limit=1000):
        if task.get("status") == "queued":
            update_task_fields(
                int(task["id"]),
                status="paused",
                error="Paused by user stop request before task started.",
            )
            paused_task_ids.append(int(task["id"]))
    return paused_task_ids


def resume_active_project_paused_tasks() -> list[int]:
    resumed_task_ids: list[int] = []
    for task in active_project_tasks(limit=1000):
        if task.get("status") == "paused":
            update_task_fields(
                int(task["id"]),
                status="queued",
                error=None,
            )
            resumed_task_ids.append(int(task["id"]))
    return resumed_task_ids


def queue_batch_summary_for_tasks(tasks: list[dict]) -> dict:
    total_count = len(tasks)
    status_counts: dict[str, int] = {}
    total_cost = 0.0
    has_cost = False

    ordered = sorted(tasks, key=lambda item: int(item.get("id") or 0))
    for task in ordered:
        status = str(task.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        amount = task.get("cost_amount_usd")
        if isinstance(amount, (int, float)):
            total_cost += float(amount)
            has_cost = True

    completed_count = status_counts.get("completed", 0)
    processing_count = status_counts.get("processing", 0)
    queued_count = status_counts.get("queued", 0)
    failed_count = status_counts.get("failed", 0) + status_counts.get("recoverable", 0)
    cancelled_count = status_counts.get("cancelled", 0)
    paused_count = status_counts.get("paused", 0)

    processing_task = next((task for task in ordered if task.get("status") == "processing"), None)
    next_queued_task = next((task for task in ordered if task.get("status") == "queued"), None)

    if processing_task:
        current_position = int(processing_task.get("queue_item_number") or (completed_count + 1))
        progress_label = f"{current_position}/{total_count} processing"
    elif next_queued_task and completed_count:
        current_position = completed_count
        progress_label = f"{completed_count}/{total_count} completed · next {next_queued_task.get('queue_item_number')}/{total_count} queued"
    elif queued_count == total_count and total_count:
        current_position = 0
        progress_label = f"0/{total_count} queued"
    elif failed_count:
        current_position = completed_count
        progress_label = f"{completed_count}/{total_count} completed · {failed_count} failed"
    else:
        current_position = completed_count
        progress_label = f"{completed_count}/{total_count} completed" if total_count else "0/0"

    return {
        "total_count": total_count,
        "completed_count": completed_count,
        "processing_count": processing_count,
        "queued_count": queued_count,
        "failed_count": failed_count,
        "cancelled_count": cancelled_count,
        "paused_count": paused_count,
        "current_position": current_position,
        "progress_label": progress_label,
        "total_cost_label": format_queue_cost_total(total_cost if has_cost else None),
        "has_active_work": processing_count > 0 or queued_count > 0,
        "has_paused_work": paused_count > 0,
    }


def output_preview_url_for_path(output_path: str | None) -> tuple[str | None, str | None]:
    if not output_path:
        return None, None

    try:
        path = Path(output_path).resolve()
        output_root = projects_module.get_output_root().resolve()
        if path.exists() and path.is_file() and path.is_relative_to(output_root):
            return str(path), "/safe-media-file?path=" + quote(str(path), safe="")
    except Exception:
        pass

    return output_path, None


def queue_group_key_for_task(task: dict) -> str:
    params = task.get("params") or {}
    for key in ("queue_group_id", "batch_import_id", "continuation_chain_id"):
        value = params.get(key)
        if value:
            return f"{key}:{value}"
    return f"task:{task.get('id')}"


def queue_display_name_for_task(task: dict) -> str:
    params = task.get("params") or {}
    return params.get("name") or params.get("single_generation_name") or params.get("scene_name") or f"Queue item #{task.get('id')}"



def last_frame_view_for_task(task: dict) -> dict:
    info = {
        "last_frame_exists": False,
        "last_frame_path": None,
        "last_frame_windows_path": None,
        "last_frame_preview_url": None,
    }

    candidates = []

    run_dir = task.get("run_dir")
    if run_dir:
        candidates.append(Path(run_dir) / "last_frame.png")

    output_path = task.get("output_path")
    if output_path:
        output = Path(output_path)
        if output.parent.name == "videos":
            candidates.append(output.parent.parent / "runs" / output.stem / "last_frame.png")

    output_root = projects_module.get_output_root().resolve()

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            continue

        if not resolved.exists() or not resolved.is_file():
            continue

        try:
            if not resolved.is_relative_to(output_root):
                continue
        except Exception:
            continue

        info["last_frame_exists"] = True
        info["last_frame_path"] = str(resolved)
        info["last_frame_windows_path"] = to_windows_path(str(resolved))
        info["last_frame_preview_url"] = "/safe-media-file?path=" + quote(str(resolved), safe="")
        return info

    return info


def queue_tasks_for_view():
    all_tasks = []
    for task in active_project_tasks(limit=1000):
        params = task.get("params") or {}
        if params.get("mode") in SINGLE_GENERATION_MODES:
            continue
        all_tasks.append(task)

    group_numbers: dict[str, int] = {}
    next_group_number = 1
    group_item_counts: dict[str, int] = {}

    for task in sorted(all_tasks, key=lambda item: int(item.get("id") or 0)):
        group_key = queue_group_key_for_task(task)
        if group_key not in group_numbers:
            group_numbers[group_key] = next_group_number
            next_group_number += 1
        group_item_counts[group_key] = group_item_counts.get(group_key, 0) + 1

    item_indexes: dict[str, int] = {}
    for task in sorted(all_tasks, key=lambda item: int(item.get("id") or 0)):
        group_key = queue_group_key_for_task(task)
        item_indexes[group_key] = item_indexes.get(group_key, 0) + 1
        group_number = group_numbers[group_key]
        item_number = item_indexes[group_key]
        params = task.get("params") or {}
        refs_view = [ref_view_for_item(item) for item in (task.get("refs") or [])]
        summary = load_summary_for_run(task.get("run_dir"))
        output_path = task.get("output_path") or summary.get("video_path")
        output_path, output_preview_url = output_preview_url_for_path(output_path)

        task["queue_group_key"] = group_key
        task["queue_number"] = group_number
        task["queue_label"] = f"Queue #{group_number}"
        task["queue_label_ru"] = f"Очередь #{group_number}"
        task["queue_item_number"] = item_number
        task["queue_item_label"] = f"{group_number}-{item_number}"
        task["queue_group_size"] = group_item_counts.get(group_key, 1)
        task["display_name"] = queue_display_name_for_task(task)
        task["output_path"] = output_path
        task["output_preview_url"] = output_preview_url
        task["output_windows_path"] = to_windows_path(output_path)
        task["output_filename"] = Path(output_path).name if output_path else None
        task["run_dir_windows_path"] = to_windows_path(task.get("run_dir"))
        task["batch_row_number"] = params.get("batch_row_number")
        task["batch_import_id"] = params.get("batch_import_id")
        task["task_mode"] = params.get("mode")
        task["is_batch_import"] = bool(params.get("batch_import_id") or params.get("batch_row_number"))
        task["refs_view"] = refs_view
        cost_info = cost_info_for_generation(summary, model=task.get("model") or params.get("model"), params=params, refs=refs_view)
        task["cost_label"] = cost_label(cost_info)
        task["cost_amount_usd"] = cost_amount_from_info(cost_info)
        task["can_edit_in_queue"] = task.get("status") == "queued"
        task["can_remove_from_queue"] = task.get("status") == "queued" and not task.get("request_id") and not task.get("output_path")
        task.update(last_frame_view_for_task(task))

    tasks = sorted(all_tasks, key=lambda item: int(item.get("id") or 0), reverse=True)[:80]

    batches = []
    batch_by_key = {}
    for task in tasks:
        group_key = task["queue_group_key"]
        if group_key not in batch_by_key:
            batch = {
                "group_key": group_key,
                "queue_number": task["queue_number"],
                "queue_label": task["queue_label"],
                "queue_label_ru": task["queue_label_ru"],
                "tasks": [],
            }
            batches.append(batch)
            batch_by_key[group_key] = batch
        batch_by_key[group_key]["tasks"].append(task)

    for batch in batches:
        batch["summary"] = queue_batch_summary_for_tasks(batch["tasks"])

    overall_summary = queue_batch_summary_for_tasks(tasks)
    return tasks, batches, overall_summary



def safe_existing_reference_refs(reference_paths: list[str]) -> list[dict]:
    refs = []

    for index, path_value in enumerate(reference_paths or [], start=1):
        if not path_value:
            continue

        try:
            resolved = Path(path_value).resolve()
        except Exception:
            continue

        media_type = reference_media_type_for_path(resolved)
        if media_type == "unsupported":
            continue

        try:
            if not resolved.exists() or not resolved.is_file():
                continue
        except Exception:
            continue

        refs.append(
            {
                "role": f"{media_type} {index}",
                "original_filename": resolved.name,
                "local_path": str(resolved),
                "source": "history_edit",
                "media_type": media_type,
                "size_bytes": resolved.stat().st_size,
            }
        )

    return refs


def single_generation_history_item_from_task(task: dict) -> dict | None:
    params = task.get("params") or {}
    if params.get("mode") not in SINGLE_GENERATION_MODES:
        return None

    refs = [ref_view_for_item(item) for item in (task.get("refs") or [])]
    summary = load_summary_for_run(task.get("run_dir"))
    output_path = task.get("output_path") or summary.get("video_path")
    output_preview_url = None

    if output_path:
        try:
            path = Path(output_path).resolve()
            output_root = projects_module.get_output_root().resolve()
            if path.exists() and path.is_file() and path.is_relative_to(output_root):
                output_preview_url = "/safe-media-file?path=" + quote(str(path), safe="")
                output_path = str(path)
        except Exception:
            output_preview_url = None

    name = params.get("single_generation_name") or params.get("name")
    if not name:
        name = params.get("episode_name") or Path(task.get("run_dir") or "Single generation").name

    processing_note = None
    processing_note_key = None
    request_id_preview = None
    if task.get("status") == "processing":
        if task.get("request_id"):
            processing_note = "Submitted to Segmind"
            processing_note_key = "segmind_submitted"
            request_id_preview = f"{str(task.get('request_id'))[:12]}..."
        elif refs:
            processing_note = "Uploading references before Segmind submit. It may not appear in Segmind yet."
            processing_note_key = "segmind_uploading_refs"
        else:
            processing_note = "Preparing Segmind submit. It may not appear in Segmind yet."
            processing_note_key = "segmind_preparing_submit"

    return {
        "source": "db",
        "task_id": task.get("id"),
        "status": task.get("status"),
        "request_id": task.get("request_id"),
        "request_id_preview": request_id_preview,
        "processing_note": processing_note,
        "processing_note_key": processing_note_key,
        "name": name,
        "prompt": task.get("prompt") or params.get("prompt") or "",
        "model": task.get("model") or params.get("model"),
        "duration": params.get("duration"),
        "resolution": params.get("resolution"),
        "aspect_ratio": params.get("aspect_ratio"),
        "seed": params.get("seed"),
        "generate_audio": params.get("generate_audio"),
        "return_last_frame": params.get("return_last_frame"),
        "refs": refs,
        "output_path": output_path,
        "output_windows_path": to_windows_path(output_path),
        "output_filename": Path(output_path).name if output_path else None,
        "output_preview_url": output_preview_url,
        "run_dir": task.get("run_dir"),
        "run_dir_windows_path": to_windows_path(task.get("run_dir")),
        "created_at": task.get("created_at"),
        "completed_at": task.get("completed_at"),
        "error": task.get("error"),
        "cost_label": cost_label_from_generation(summary, model=task.get("model") or params.get("model"), params=params, refs=refs),
    }


def single_generation_history_from_legacy_runs(seen_run_dirs: set[str], limit: int = 20) -> list[dict]:
    gui_runs_dir = projects_module.get_active_project_dir() / "gui_runs"
    if not gui_runs_dir.exists():
        return []

    items = []
    for run_dir in sorted(gui_runs_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if len(items) >= limit:
            break

        if not run_dir.is_dir() or str(run_dir.resolve()) in seen_run_dirs:
            continue

        params = {}
        refs = []
        summary = {}
        error = None

        try:
            params_path = run_dir / "params.json"
            if params_path.exists():
                params = json.loads(params_path.read_text(encoding="utf-8"))

            refs_path = run_dir / "refs.json"
            if refs_path.exists():
                refs = json.loads(refs_path.read_text(encoding="utf-8"))

            summary_path = run_dir / "summary.json"
            if summary_path.exists():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))

            error_path = run_dir / "errors.log"
            if error_path.exists():
                error = error_path.read_text(encoding="utf-8")[:1000]
        except Exception:
            continue

        video_path = summary.get("video_path") or str(run_dir / "output.mp4")
        if not Path(video_path).exists():
            video_path = None

        output_preview_url = None
        if video_path:
            output_preview_url = "/safe-media-file?path=" + quote(str(Path(video_path).resolve()), safe="")

        prompt = ""
        prompt_path = run_dir / "prompt.txt"
        if prompt_path.exists():
            prompt = prompt_path.read_text(encoding="utf-8")
        else:
            prompt = params.get("prompt") or ""

        status = summary.get("status") or ("failed" if error else "completed")
        cost_label = cost_label_from_generation(summary, model=summary.get("model") or params.get("model"), params=params, refs=refs)

        items.append(
            {
                "source": "legacy_run",
                "task_id": None,
                "status": status,
                "name": params.get("single_generation_name") or run_dir.name,
                "prompt": prompt,
                "model": summary.get("model") or params.get("model"),
                "duration": params.get("duration"),
                "resolution": params.get("resolution"),
                "aspect_ratio": params.get("aspect_ratio"),
                "seed": params.get("seed"),
                "generate_audio": params.get("generate_audio"),
                "return_last_frame": params.get("return_last_frame"),
                "refs": [ref_view_for_item(item) for item in refs],
                "output_path": video_path,
                "output_windows_path": to_windows_path(video_path),
                "output_filename": Path(video_path).name if video_path else None,
                "output_preview_url": output_preview_url,
                "run_dir": str(run_dir),
                "run_dir_windows_path": to_windows_path(str(run_dir)),
                "created_at": datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat(timespec="seconds"),
                "completed_at": None,
                "error": error,
            }
        )

    return items


def single_generation_history_for_view(limit: int = 40) -> list[dict]:
    items = []
    seen_run_dirs = set()

    for task in active_project_tasks(limit=1000):
        item = single_generation_history_item_from_task(task)
        if not item:
            continue
        if item.get("run_dir"):
            try:
                seen_run_dirs.add(str(Path(item["run_dir"]).resolve()))
            except Exception:
                pass
        items.append(item)
        if len(items) >= limit:
            break

    remaining = max(0, limit - len(items))
    if remaining:
        items.extend(single_generation_history_from_legacy_runs(seen_run_dirs, remaining))

    return items[:limit]


def redirect_home(message: str | None = None) -> RedirectResponse:
    url = "/"
    if message:
        url = f"/?message={quote(message)}"
    return RedirectResponse(url=url, status_code=303)


def base_context(
    request: Request,
    message: str | None = None,
    last_draft: dict | None = None,
    last_run: dict | None = None,
    last_queue_add: dict | None = None,
    last_queue_run: dict | None = None,
    batch_import_report: dict | None = None,
    night_mode_report: dict | None = None,
):
    if message is None and request is not None:
        message = request.query_params.get("message")

    queue_tasks, queue_batches, queue_overall_summary = queue_tasks_for_view()
    single_history = single_generation_history_for_view()
    queue_loop_state = queue_loop_state_for_active_project()
    has_active_queue_work = bool(
        queue_loop_state.get("active")
        or any(item.get("status") == "processing" for item in queue_tasks)
    )

    context = {
        "request": request,
        "app_version": "0.1.0",
        "app_title": APP_TITLE,
        "app_subtitle": APP_SUBTITLE,
        "api_key_set": env_key_is_set(),
        "api_base": SEGMIND_API_BASE,
        **segmind_balance_context(),
        "default_model": SEGMIND_MODEL,
        "model_choices": MODEL_CHOICES,
        "output_dir": str(projects_module.get_active_project_dir()),
        "durations": DURATIONS,
        "resolutions": RESOLUTIONS,
        "aspect_ratios": ASPECT_RATIOS,
        "message": message,
        "last_draft": last_draft,
        "last_run": last_run,
        "last_queue_add": last_queue_add,
        "last_queue_run": last_queue_run,
        "batch_import_report": batch_import_report,
        "night_mode_report": night_mode_report,
        "queue_tasks": queue_tasks,
        "queue_batches": queue_batches,
        "queue_overall_summary": queue_overall_summary,
        "queue_loop_state": queue_loop_state,
        "has_active_queue_work": has_active_queue_work,
        "refresh_seconds": QUEUE_LOOP_REFRESH_SECONDS,
        "single_history": single_history,
        "has_processing_single_generation": any(item.get("status") in {"queued", "processing"} for item in single_history[:20]),
    }

    context.update(project_context())

    return context

def cleanup_processing_without_request_id(limit: int = 20) -> dict:
    tasks = active_project_tasks(limit=1000)

    candidates = [
        task for task in tasks
        if task.get("status") == "processing"
        and not task.get("request_id")
    ]

    changed = []

    for task in candidates[:limit]:
        task_id = int(task["id"])
        update_task_fields(
            task_id,
            status="failed",
            error="Stale processing task without request_id after restart. Cannot recover automatically; use Retry later.",
        )
        changed.append(task_id)

    return {
        "checked_count": len(candidates[:limit]),
        "failed_count": len(changed),
        "task_ids": changed,
        "new_paid_submit": False,
    }


def auto_recover_existing_requests(limit: int = 20) -> dict:
    tasks = active_project_tasks(limit=1000)

    candidates = [
        task for task in tasks
        if task.get("status") in ["processing", "recoverable"]
        and task.get("request_id")
        and not task.get("output_path")
    ]

    results = []

    for task in candidates[:limit]:
        result = recover_task_by_existing_request(int(task["id"]))
        results.append(result)

    completed = len([item for item in results if item.get("status") == "completed"])

    return {
        "checked_count": len(candidates[:limit]),
        "completed_count": completed,
        "results": results,
        "new_paid_submit": False,
    }



def normalize_prompt_reference_tokens(prompt: str, refs: list[dict]) -> str:
    result = prompt or ""
    filenames = []

    for ref in refs or []:
        filename = ref.get("original_filename") or ref.get("filename")
        if isinstance(filename, str) and filename:
            filenames.append(filename)

    for filename in sorted(set(filenames), key=len, reverse=True):
        escaped = re.escape(filename)
        result = re.sub(rf"(?<!<)@{escaped}(?!>)", f"<@{filename}>", result)

    return result


def normalize_model(model: str) -> str:
    allowed_models = {item["id"] for item in MODEL_CHOICES}
    return model if model in allowed_models else "seedance-2.0"


def build_params(
    *,
    model: str,
    prompt: str,
    saved_refs: list[dict],
    duration: int,
    resolution: str,
    aspect_ratio: str,
    episode_name: str,
    scene_name: str,
    seed: int,
    generate_audio: str | None,
    return_last_frame: str | None,
    mode: str,
) -> dict:
    return {
        "project_name": projects_module.get_active_project_name(),
        "project_dir": str(projects_module.get_active_project_dir()),
        "episode_name": episode_name.strip() or "Episode_01",
        "scene_name": scene_name.strip() or "Scene_001",
        "model": model,
        "prompt": prompt,
        "reference_images": [item["local_path"] for item in saved_refs if item.get("media_type") in (None, "image")],
        "reference_videos": [item["local_path"] for item in saved_refs if item.get("media_type") == "video"],
        "reference_audios": [item["local_path"] for item in saved_refs if item.get("media_type") == "audio"],
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "generate_audio": bool(generate_audio),
        "seed": seed,
        "return_last_frame": bool(return_last_frame),
        "skip_moderation": False,
        "mode": mode,
    }


def parse_chain_prompts(chain_prompts: str, max_items: int = 20) -> list[str]:
    blocks = []
    current_lines = []

    for raw_line in (chain_prompts or "").splitlines():
        if raw_line.strip() == "---":
            block = "\n".join(current_lines).strip()
            if block:
                blocks.append(block)
            current_lines = []
            continue

        current_lines.append(raw_line)

    final_block = "\n".join(current_lines).strip()
    if final_block:
        blocks.append(final_block)

    if len(blocks) < 2:
        raise ValueError("Add at least 2 prompt items separated by a line containing only ---.")

    return blocks[:max_items]


def create_continuation_chain_tasks(
    *,
    prompts: list[str],
    model: str,
    saved_refs: list[dict],
    duration: int,
    resolution: str,
    aspect_ratio: str,
    episode_name: str,
    scene_name: str,
    seed: int,
    generate_audio: str | None,
    chain_id: str,
    create_task_fn=None,
) -> dict:
    if create_task_fn is None:
        create_task_fn = create_task

    created_tasks = []
    previous_task_id = None

    for index, prompt in enumerate(prompts, start=1):
        refs = saved_refs if index == 1 else []
        params = {
            "project_name": projects_module.get_active_project_name(),
            "project_dir": str(projects_module.get_active_project_dir()),
            "episode_name": episode_name.strip() or "Episode_01",
            "scene_name": scene_name.strip() or "Scene_001",
            "model": model,
            "prompt": prompt,
            "reference_images": [item["local_path"] for item in refs],
            "reference_videos": [],
            "reference_audios": [],
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "generate_audio": bool(generate_audio),
            "seed": seed,
            "return_last_frame": True,
            "skip_moderation": False,
            "mode": "continuation_chain_queued_no_generation_yet",
            "continuation_chain_id": chain_id,
            "continuation_index": index,
        }

        if previous_task_id is not None:
            params["continuation_mode"] = "last_frame_as_reference"
            params["parent_task_id"] = previous_task_id

        task_id = create_task_fn(
            model=model,
            prompt=prompt,
            params=params,
            refs=refs,
            status="queued",
        )

        created_tasks.append(
            {
                "task_id": task_id,
                "prompt": prompt,
                "params": params,
                "refs": refs,
            }
        )
        previous_task_id = task_id

    return {
        "chain_id": chain_id,
        "created_tasks": created_tasks,
    }


def parse_generate_audio_value(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if normalized == "":
        return False

    if normalized in {"true", "1", "yes", "y"}:
        return True

    if normalized in {"false", "0", "no", "n"}:
        return False

    raise ValueError("Use true/false, 1/0, yes/no, y/n, or leave empty.")


def parse_batch_csv_text(csv_text: str) -> dict:
    lines = (csv_text or "").lstrip("\ufeff").splitlines()
    if not lines:
        return {
            "rows": [],
            "errors": [{"row": 1, "field": "csv_file", "message": "CSV file is empty."}],
        }

    reader = csv.DictReader(lines)
    headers = reader.fieldnames or []
    missing = [name for name in BATCH_IMPORT_REQUIRED_COLUMNS if name not in headers]

    if missing:
        return {
            "rows": [],
            "errors": [
                {
                    "row": 1,
                    "field": "header",
                    "message": "Missing required columns: " + ", ".join(missing),
                }
            ],
        }

    rows = []
    for row_number, row in enumerate(reader, start=2):
        rows.append(
            {
                "row_number": row_number,
                "raw": {key: (value if value is not None else "") for key, value in row.items()},
            }
        )

    return {
        "rows": rows,
        "errors": [],
    }


def validate_batch_import_row(row: dict) -> tuple[dict | None, list[dict]]:
    row_number = row["row_number"]
    raw = row["raw"]
    errors = []

    def add_error(field: str, message: str) -> None:
        errors.append({"row": row_number, "field": field, "message": message})

    prompt = (raw.get("prompt") or "").strip()
    if not prompt:
        add_error("prompt", "Prompt is required.")

    episode_name = (raw.get("episode_name") or "").strip() or "Episode_01"
    scene_name = (raw.get("scene_name") or "").strip() or "Scene_001"

    model = (raw.get("model") or "").strip() or "seedance-2.0-fast"
    allowed_models = {item["id"] for item in MODEL_CHOICES}
    if model not in allowed_models:
        add_error("model", f"Invalid model: {model}")

    duration_text = (raw.get("duration") or "").strip()
    duration = 4
    if duration_text:
        try:
            duration = int(duration_text)
        except ValueError:
            add_error("duration", "Duration must be an integer.")
    if duration not in DURATIONS:
        add_error("duration", f"Duration must be one of: {', '.join(str(item) for item in DURATIONS)}")

    resolution = (raw.get("resolution") or "").strip() or "480p"
    if resolution not in RESOLUTIONS:
        add_error("resolution", f"Resolution must be one of: {', '.join(RESOLUTIONS)}")

    aspect_ratio = (raw.get("aspect_ratio") or "").strip() or "16:9"
    if aspect_ratio not in ASPECT_RATIOS:
        add_error("aspect_ratio", f"Aspect ratio must be one of: {', '.join(ASPECT_RATIOS)}")

    seed_text = (raw.get("seed") or "").strip()
    seed = -1
    if seed_text:
        try:
            seed = int(seed_text)
        except ValueError:
            add_error("seed", "Seed must be an integer.")

    try:
        generate_audio = parse_generate_audio_value(raw.get("generate_audio") or "")
    except ValueError as exc:
        generate_audio = False
        add_error("generate_audio", str(exc))

    continuation_group = (raw.get("continuation_group") or "").strip()
    continuation_index_text = (raw.get("continuation_index") or "").strip()
    continuation_index = None
    if continuation_index_text:
        try:
            continuation_index = int(continuation_index_text)
        except ValueError:
            add_error("continuation_index", "Continuation index must be an integer.")
        if not continuation_group:
            add_error("continuation_index", "Continuation index requires continuation_group.")

    reference_paths = []
    reference_paths_text = raw.get("reference_paths") or ""
    for item in reference_paths_text.split(";"):
        path_text = item.strip()
        if not path_text:
            continue

        path = Path(path_text)
        if not path.exists():
            add_error("reference_paths", f"Reference path does not exist: {path_text}")
            continue

        if not path.is_file():
            add_error("reference_paths", f"Reference path is not a file: {path_text}")
            continue

        if path.suffix.lower() not in REFERENCE_IMAGE_SUFFIXES:
            add_error("reference_paths", f"Reference image must be .png, .jpg, .jpeg or .webp: {path_text}")
            continue

        reference_paths.append(str(path))

    if errors:
        return None, errors

    return {
        "row_number": row_number,
        "episode_name": episode_name,
        "scene_name": scene_name,
        "prompt": prompt,
        "model": model,
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "seed": seed,
        "generate_audio": generate_audio,
        "reference_paths": reference_paths,
        "continuation_group": continuation_group,
        "continuation_index": continuation_index,
    }, []


def validate_batch_import_rows(rows: list[dict]) -> dict:
    valid_rows = []
    errors = []

    for row in rows:
        valid_row, row_errors = validate_batch_import_row(row)
        errors.extend(row_errors)
        if valid_row:
            valid_rows.append(valid_row)

    return {
        "valid_rows": valid_rows,
        "errors": errors,
    }


def parse_and_validate_batch_csv(csv_text: str) -> dict:
    parsed = parse_batch_csv_text(csv_text)
    if parsed["errors"]:
        return {
            "rows": parsed["rows"],
            "valid_rows": [],
            "errors": parsed["errors"],
        }

    validation = validate_batch_import_rows(parsed["rows"])
    return {
        "rows": parsed["rows"],
        "valid_rows": validation["valid_rows"],
        "errors": validation["errors"],
    }


def refs_from_reference_paths(reference_paths: list[str], row_number: int) -> list[dict]:
    refs = []
    for index, path in enumerate(reference_paths, start=1):
        resolved = Path(path)
        refs.append(
            {
                "role": f"batch row {row_number} image {index}",
                "original_filename": resolved.name,
                "local_path": str(resolved),
                "source": "batch_csv_import",
                "batch_row_number": row_number,
                "size_bytes": resolved.stat().st_size,
            }
        )

    return refs


def create_batch_import_tasks(
    *,
    valid_rows: list[dict],
    batch_import_id: str,
    create_task_fn=None,
) -> dict:
    if create_task_fn is None:
        create_task_fn = create_task

    created_tasks = []
    previous_task_by_group: dict[str, int] = {}
    count_by_group: dict[str, int] = {}
    continuation_link_count = 0

    for row in valid_rows:
        refs = refs_from_reference_paths(row["reference_paths"], row["row_number"])
        continuation_group = (row.get("continuation_group") or "").strip()
        continuation_index = row.get("continuation_index")
        if continuation_group:
            count_by_group[continuation_group] = count_by_group.get(continuation_group, 0) + 1
            if continuation_index is None:
                continuation_index = count_by_group[continuation_group]
        params = {
            "project_name": projects_module.get_active_project_name(),
            "project_dir": str(projects_module.get_active_project_dir()),
            "episode_name": row["episode_name"],
            "scene_name": row["scene_name"],
            "model": row["model"],
            "prompt": row["prompt"],
            "reference_images": [item["local_path"] for item in refs],
            "reference_videos": [],
            "reference_audios": [],
            "duration": row["duration"],
            "resolution": row["resolution"],
            "aspect_ratio": row["aspect_ratio"],
            "generate_audio": row["generate_audio"],
            "seed": row["seed"],
            "return_last_frame": True,
            "skip_moderation": False,
            "mode": "batch_import_queued_no_generation_yet",
            "batch_import_id": batch_import_id,
            "batch_row_number": row["row_number"],
        }

        if continuation_group:
            params["continuation_chain_id"] = f"{batch_import_id}_{sanitize_folder_part(continuation_group, 'chain')}"
            params["continuation_index"] = continuation_index
            parent_task_id = previous_task_by_group.get(continuation_group)
            if parent_task_id is not None:
                params["continuation_mode"] = "last_frame_as_reference"
                params["parent_task_id"] = parent_task_id
                continuation_link_count += 1

        task_id = create_task_fn(
            model=row["model"],
            prompt=row["prompt"],
            params=params,
            refs=refs,
            status="queued",
        )

        if continuation_group:
            previous_task_by_group[continuation_group] = task_id

        created_tasks.append(
            {
                "task_id": task_id,
                "row_number": row["row_number"],
                "params": params,
                "refs": refs,
            }
        )

    return {
        "batch_import_id": batch_import_id,
        "created_tasks": created_tasks,
        "continuation_group_count": len(count_by_group),
        "continuation_link_count": continuation_link_count,
    }


def parse_limited_int(value: str | int | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    return max(minimum, min(maximum, parsed))


def build_night_mode_preview_plan(
    *,
    max_tasks: int,
    stop_on_consecutive_errors: int,
    tasks: list[dict] | None = None,
) -> dict:
    if tasks is None:
        tasks = active_project_tasks(limit=1000)

    queued_tasks = [task for task in tasks if task.get("status") == "queued"]
    selected_tasks = queued_tasks[:max_tasks]
    completed_task_ids = {
        int(task["id"])
        for task in tasks
        if task.get("status") == "completed" and task.get("id") is not None
    }
    selected_task_ids = {
        int(task["id"])
        for task in selected_tasks
        if task.get("id") is not None
    }

    task_summaries = []
    dependent_continuation_count = 0
    blocked_by_parent_count = 0

    for index, task in enumerate(selected_tasks, start=1):
        params = task.get("params") or {}
        parent_task_id = params.get("parent_task_id")
        continuation_mode = params.get("continuation_mode")
        is_dependent = continuation_mode == "last_frame_as_reference" and parent_task_id is not None
        parent_ready = True

        if is_dependent:
            dependent_continuation_count += 1
            try:
                parent_id_int = int(parent_task_id)
            except (TypeError, ValueError):
                parent_id_int = None

            parent_ready = parent_id_int in completed_task_ids or parent_id_int in selected_task_ids
            if not parent_ready:
                blocked_by_parent_count += 1

        task_summaries.append(
            {
                "index": index,
                "task_id": task.get("id"),
                "model": task.get("model") or params.get("model"),
                "episode_name": params.get("episode_name") or "Episode_01",
                "scene_name": params.get("scene_name") or "Scene_001",
                "continuation_mode": continuation_mode,
                "parent_task_id": parent_task_id,
                "parent_ready": parent_ready,
                "prompt": (task.get("prompt") or "")[:160],
            }
        )

    return {
        "status": "preview",
        "max_tasks": max_tasks,
        "stop_on_consecutive_errors": stop_on_consecutive_errors,
        "queued_count": len(queued_tasks),
        "selected_count": len(selected_tasks),
        "dependent_continuation_count": dependent_continuation_count,
        "blocked_by_parent_count": blocked_by_parent_count,
        "no_parallel_dependent_continuation_chains": True,
        "new_paid_submit_started": False,
        "tasks": task_summaries,
    }


def extract_output_url(data):
    if not isinstance(data, dict):
        return None

    candidates = []

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


def download_file(url: str, path: Path) -> None:
    with httpx.stream("GET", url, timeout=300.0) as response:
        response.raise_for_status()
        with path.open("wb") as f:
            for chunk in response.iter_bytes():
                if chunk:
                    f.write(chunk)


async def save_uploaded_refs(reference_images: list[UploadFile], refs_dir: Path) -> list[dict]:
    refs_dir.mkdir(parents=True, exist_ok=True)
    saved_refs = []

    for index, uploaded in enumerate(reference_images, start=1):
        if not uploaded.filename:
            continue

        safe_name = Path(uploaded.filename).name
        suffix = Path(safe_name).suffix.lower()

        if suffix not in [".png", ".jpg", ".jpeg", ".webp"]:
            continue

        target_path = refs_dir / f"reference_{index:02d}{suffix}"

        with target_path.open("wb") as f:
            shutil.copyfileobj(uploaded.file, f)

        saved_refs.append({
            "role": f"image {index}",
            "original_filename": safe_name,
            "local_path": str(target_path),
            "size_bytes": target_path.stat().st_size,
        })

    return saved_refs


async def save_uploaded_reference_files(reference_files: list[UploadFile], refs_dir: Path, source: str = "ui_upload") -> list[dict]:
    refs_dir.mkdir(parents=True, exist_ok=True)
    saved_refs = []

    for index, uploaded in enumerate(reference_files or [], start=1):
        if not uploaded.filename:
            continue

        media_type = reference_media_type_for_path(uploaded.filename)
        if media_type == "unsupported":
            continue

        safe_name = sanitize_reference_filename(uploaded.filename, f"reference_{index:02d}")
        suffix = Path(safe_name).suffix.lower()
        target_path = refs_dir / f"reference_{index:02d}_{Path(safe_name).stem}{suffix}"

        with target_path.open("wb") as f:
            shutil.copyfileobj(uploaded.file, f)

        saved_refs.append(
            {
                "role": f"{media_type} {index}",
                "original_filename": Path(uploaded.filename).name,
                "local_path": str(target_path),
                "source": source,
                "media_type": media_type,
                "size_bytes": target_path.stat().st_size,
            }
        )

    return saved_refs


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", base_context(request))




@app.post("/set-active-project", response_class=HTMLResponse)
def set_active_project_endpoint(request: Request, project_name: str = Form("")):
    try:
        state = projects_module.set_active_project(project_name)
        message = f"Active project switched to '{state['active_project_name']}'."
    except Exception as exc:
        message = f"Active project was not changed: {type(exc).__name__}: {exc}"

    return templates.TemplateResponse(
        "index.html",
        base_context(request, message=message),
    )



@app.post("/update-api-settings", response_class=HTMLResponse)
def update_api_settings_endpoint(
    request: Request,
    segmind_api_key: str = Form(""),
    segmind_api_base: str = Form(""),
    default_model: str = Form("seedance-2.0"),
):
    updates = {}
    api_key = (segmind_api_key or "").strip()
    api_base = (segmind_api_base or "").strip()
    model = normalize_model(default_model)

    if api_key:
        updates["SEGMIND_API_KEY"] = api_key
    if api_base:
        updates["SEGMIND_API_BASE"] = api_base
    updates["SEGMIND_MODEL"] = model

    try:
        update_env_values(updates)
        message = "API settings were saved. Restart the GUI to use the new key/model for new generations."
    except Exception as exc:
        message = f"API settings were not saved: {type(exc).__name__}: {exc}"

    return templates.TemplateResponse(
        "index.html",
        base_context(request, message=message),
    )


@app.post("/delete-project", response_class=HTMLResponse)
def delete_project_endpoint(request: Request, project_name: str = Form("")):
    try:
        safe_name = projects_module.sanitize_project_name(project_name)
        active_name = projects_module.get_active_project_name()
        if safe_name == active_name:
            raise ValueError("Switch to another project before deleting the active project.")

        output_root = projects_module.get_output_root().resolve()
        project_dir = projects_module.get_project_dir(safe_name).resolve()
        if not project_dir.is_relative_to(output_root):
            raise ValueError("Project path is outside output root.")
        if not project_dir.exists():
            raise ValueError("Project folder does not exist.")

        shutil.rmtree(project_dir)
        message = f"Project '{safe_name}' was deleted."
    except Exception as exc:
        message = f"Project was not deleted: {type(exc).__name__}: {exc}"

    return templates.TemplateResponse(
        "index.html",
        base_context(request, message=message),
    )


@app.post("/create-project", response_class=HTMLResponse)
def create_project_endpoint(request: Request, project_name: str = Form("")):
    try:
        project_dir = projects_module.create_project(project_name)
        message = (
            f"Project '{project_dir.name}' was created in the output root. "
            "Active project was not changed yet."
        )
    except Exception as exc:
        message = f"Project was not created: {type(exc).__name__}: {exc}"

    return templates.TemplateResponse(
        "index.html",
        base_context(request, message=message),
    )


@app.post("/add-to-queue", response_class=HTMLResponse)
async def add_to_queue(
    request: Request,
    prompt: str = Form(""),
    model: str = Form("seedance-2.0"),
    duration: int = Form(4),
    resolution: str = Form("480p"),
    aspect_ratio: str = Form("16:9"),
    episode_name: str = Form("Episode_01"),
    scene_name: str = Form("Scene_001"),
    seed: int = Form(-1),
    generate_audio: str | None = Form(None),
    return_last_frame: str | None = Form(None),
    reference_files: list[UploadFile] = File(default=[]),
    existing_reference_paths: list[str] = Form(default=[]),
):
    model = normalize_model(model)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    queue_dir = projects_module.get_active_project_dir() / "queue_tasks" / f"queued_{timestamp}"
    refs_dir = queue_dir / "refs"
    queue_dir.mkdir(parents=True, exist_ok=True)

    saved_refs = safe_existing_reference_refs(existing_reference_paths)
    saved_refs.extend(await save_uploaded_reference_files(reference_files, refs_dir, source="queue_upload"))
    prompt = normalize_prompt_reference_tokens(prompt, saved_refs)

    queue_group_id = f"manual_{timestamp}_{uuid.uuid4().hex[:8]}"

    params = build_params(
        model=model,
        prompt=prompt,
        saved_refs=saved_refs,
        duration=duration,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        episode_name=episode_name,
        scene_name=scene_name,
        seed=seed,
        generate_audio=generate_audio,
        return_last_frame=return_last_frame,
        mode="queued_no_generation_yet",
    )
    params["queue_group_id"] = queue_group_id

    task_id = create_task(
        model=model,
        prompt=prompt,
        params=params,
        refs=saved_refs,
        status="queued",
    )

    queue_task_dir = task_project_dir / "queue_tasks" / f"task_{task_id:06d}"
    queue_task_dir.mkdir(parents=True, exist_ok=True)

    (queue_task_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (queue_task_dir / "params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")
    (queue_task_dir / "refs.json").write_text(json.dumps(saved_refs, indent=2, ensure_ascii=False), encoding="utf-8")
    (queue_task_dir / "task_id.txt").write_text(str(task_id), encoding="utf-8")

    last_queue_add = {
        "task_id": task_id,
        "status": "queued",
        "model": model,
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "refs_count": len(saved_refs),
        "task_dir": str(queue_task_dir),
    }

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=f"Task #{task_id} added to queue. No paid generation was started.",
            last_queue_add=last_queue_add,
        ),
    )



@app.post("/update-queued-task/{task_id}", response_class=HTMLResponse)
async def update_queued_task(
    task_id: int,
    request: Request,
    prompt: str = Form(""),
    model: str = Form("seedance-2.0"),
    duration: int = Form(4),
    resolution: str = Form("480p"),
    aspect_ratio: str = Form("16:9"),
    episode_name: str = Form("Episode_01"),
    scene_name: str = Form("Scene_001"),
    seed: int = Form(-1),
    generate_audio: str | None = Form(None),
    return_last_frame: str | None = Form(None),
    reference_files: list[UploadFile] = File(default=[]),
    existing_reference_paths: list[str] = Form(default=[]),
):
    task = get_task(task_id)
    if not task:
        message = f"Queue item #{task_id} was not found."
        return templates.TemplateResponse("index.html", base_context(request, message=message), status_code=404)

    if task.get("status") != "queued":
        message = f"Queue item #{task_id} is already {task.get('status')} and cannot be edited in queue."
        return templates.TemplateResponse("index.html", base_context(request, message=message))

    model = normalize_model(model)
    task_project_dir = Path((task.get("params") or {}).get("project_dir") or projects_module.get_active_project_dir())
    refs_dir = task_project_dir / "queue_tasks" / f"task_{task_id:06d}" / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)

    saved_refs = safe_existing_reference_refs(existing_reference_paths)
    saved_refs.extend(await save_uploaded_reference_files(reference_files, refs_dir, source="queue_edit_upload"))
    prompt = normalize_prompt_reference_tokens(prompt, saved_refs)

    old_params = task.get("params") or {}
    params = build_params(
        model=model,
        prompt=prompt,
        saved_refs=saved_refs,
        duration=duration,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        episode_name=episode_name,
        scene_name=scene_name,
        seed=seed,
        generate_audio=generate_audio,
        return_last_frame=return_last_frame,
        mode=old_params.get("mode") or "queued_no_generation_yet",
    )
    for key in ("project_dir", "queue_group_id", "batch_import_id", "batch_row_number", "continuation_chain_id", "continuation_index"):
        if key in old_params:
            params[key] = old_params[key]

    update_task_payload(task_id, model=model, prompt=prompt, params=params, refs=saved_refs)

    queue_task_dir = task_project_dir / "queue_tasks" / f"task_{task_id:06d}"
    queue_task_dir.mkdir(parents=True, exist_ok=True)
    (queue_task_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (queue_task_dir / "params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")
    (queue_task_dir / "refs.json").write_text(json.dumps(saved_refs, indent=2, ensure_ascii=False), encoding="utf-8")
    (queue_task_dir / "task_id.txt").write_text(str(task_id), encoding="utf-8")

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=f"Queue item #{task_id} was updated in place. No paid generation was started.",
        ),
    )


@app.post("/remove-queued-task/{task_id}", response_class=HTMLResponse)
def remove_queued_task(task_id: int, request: Request):
    task = get_task(task_id)
    if not task:
        message = f"Queue item #{task_id} was not found."
        return templates.TemplateResponse("index.html", base_context(request, message=message), status_code=404)

    if task.get("status") != "queued" or task.get("request_id") or task.get("output_path"):
        message = f"Queue item #{task_id} is not a removable queued item."
        return templates.TemplateResponse("index.html", base_context(request, message=message))

    delete_task(task_id)
    return templates.TemplateResponse(
        "index.html",
        base_context(request, message=f"Queue item #{task_id} was removed from the queue. Generated files were not touched."),
    )


@app.post("/add-continuation-chain", response_class=HTMLResponse)
async def add_continuation_chain(
    request: Request,
    chain_prompts: str = Form(""),
    model: str = Form("seedance-2.0-fast"),
    duration: int = Form(4),
    resolution: str = Form("480p"),
    aspect_ratio: str = Form("16:9"),
    chain_episode_name: str = Form("Episode_01"),
    chain_scene_name: str = Form("Scene_001"),
    seed: int = Form(-1),
    generate_audio: str | None = Form(None),
    reference_files: list[UploadFile] = File(default=[]),
):
    model = normalize_model(model)

    try:
        prompts = parse_chain_prompts(chain_prompts)
    except ValueError as exc:
        return templates.TemplateResponse(
            "index.html",
            base_context(request, message=str(exc)),
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chain_id = f"chain_{timestamp}_{uuid.uuid4().hex[:8]}"
    queue_dir = projects_module.get_active_project_dir() / "queue_tasks" / chain_id
    refs_dir = queue_dir / "shared_refs"
    queue_dir.mkdir(parents=True, exist_ok=True)

    saved_refs = await save_uploaded_reference_files(reference_files, refs_dir, source="chain_upload")
    prompts = [normalize_prompt_reference_tokens(item, saved_refs) for item in prompts]

    chain_result = create_continuation_chain_tasks(
        prompts=prompts,
        model=model,
        saved_refs=saved_refs,
        duration=duration,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        episode_name=chain_episode_name,
        scene_name=chain_scene_name,
        seed=seed,
        generate_audio=generate_audio,
        chain_id=chain_id,
    )

    for item in chain_result["created_tasks"]:
        queue_task_dir = projects_module.get_active_project_dir() / "queue_tasks" / f"task_{int(item['task_id']):06d}"
        queue_task_dir.mkdir(parents=True, exist_ok=True)

        (queue_task_dir / "prompt.txt").write_text(item["prompt"], encoding="utf-8")
        (queue_task_dir / "params.json").write_text(
            json.dumps(item["params"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (queue_task_dir / "refs.json").write_text(
            json.dumps(item["refs"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (queue_task_dir / "task_id.txt").write_text(str(item["task_id"]), encoding="utf-8")

    first_task_id = chain_result["created_tasks"][0]["task_id"]
    last_task_id = chain_result["created_tasks"][-1]["task_id"]

    last_queue_add = {
        "task_id": f"{first_task_id}-{last_task_id}",
        "status": "queued",
        "model": model,
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "refs_count": len(saved_refs),
        "task_dir": str(queue_dir),
    }

    message = (
        f"Continuation chain {chain_id} added to queue with {len(chain_result['created_tasks'])} tasks. "
        "No paid generation was started."
    )

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=message,
            last_queue_add=last_queue_add,
        ),
    )


@app.post("/batch-import", response_class=HTMLResponse)
async def batch_import(
    request: Request,
    import_mode: str = Form("preview"),
    csv_file: UploadFile = File(...),
):
    if import_mode not in {"preview", "confirm"}:
        import_mode = "preview"

    try:
        csv_bytes = await csv_file.read()
        csv_text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        report = {
            "mode": import_mode,
            "status": "error",
            "total_rows": 0,
            "valid_rows": 0,
            "created_count": 0,
            "created_task_ids": [],
            "errors": [{"row": 1, "field": "csv_file", "message": "CSV must be UTF-8 encoded."}],
            "new_paid_submit_started": False,
        }
        return templates.TemplateResponse(
            "index.html",
            base_context(
                request,
                message="CSV import has errors. No queued tasks were created.",
                batch_import_report=report,
            ),
        )

    parsed = parse_and_validate_batch_csv(csv_text)
    errors = parsed["errors"]
    valid_rows = parsed["valid_rows"]
    report = {
        "mode": import_mode,
        "status": "preview" if import_mode == "preview" else "error",
        "total_rows": len(parsed["rows"]),
        "valid_rows": len(valid_rows),
        "created_count": 0,
        "created_task_ids": [],
        "errors": errors,
        "new_paid_submit_started": False,
    }

    if errors:
        report["status"] = "error"
        return templates.TemplateResponse(
            "index.html",
            base_context(
                request,
                message="CSV import has errors. No queued tasks were created.",
                batch_import_report=report,
            ),
        )

    if import_mode == "preview":
        return templates.TemplateResponse(
            "index.html",
            base_context(
                request,
                message=f"CSV import preview: {len(valid_rows)} valid row(s). No queued tasks were created.",
                batch_import_report=report,
            ),
        )

    batch_import_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    batch_result = create_batch_import_tasks(
        valid_rows=valid_rows,
        batch_import_id=batch_import_id,
    )
    created_task_ids = [item["task_id"] for item in batch_result["created_tasks"]]
    report.update(
        {
            "status": "created",
            "batch_import_id": batch_import_id,
            "created_count": len(created_task_ids),
            "created_task_ids": created_task_ids,
            "continuation_group_count": batch_result.get("continuation_group_count", 0),
            "continuation_link_count": batch_result.get("continuation_link_count", 0),
        }
    )

    last_queue_add = {
        "task_id": ", ".join(str(item) for item in created_task_ids),
        "status": "queued",
        "model": "batch import",
        "duration": "mixed",
        "resolution": "mixed",
        "aspect_ratio": "mixed",
        "refs_count": sum(len(item["refs"]) for item in batch_result["created_tasks"]),
        "task_dir": f"batch_import_id={batch_import_id}",
    }

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=f"CSV import created {len(created_task_ids)} queued task(s). No paid generation was started.",
            last_queue_add=last_queue_add,
            batch_import_report=report,
        ),
    )


@app.post("/night-mode-preview", response_class=HTMLResponse)
def night_mode_preview(
    request: Request,
    max_tasks: int = Form(5),
    stop_on_consecutive_errors: int = Form(1),
):
    max_tasks = parse_limited_int(max_tasks, default=5, minimum=1, maximum=50)
    stop_on_consecutive_errors = parse_limited_int(
        stop_on_consecutive_errors,
        default=1,
        minimum=1,
        maximum=10,
    )
    report = build_night_mode_preview_plan(
        max_tasks=max_tasks,
        stop_on_consecutive_errors=stop_on_consecutive_errors,
    )

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=(
                f"Night Mode preview selected {report['selected_count']} queued task(s). "
                "No paid generation was started."
            ),
            night_mode_report=report,
        ),
    )



@app.post("/start-queue-once", response_class=HTMLResponse)
def start_queue_once(request: Request):
    stale_cleanup = cleanup_processing_without_request_id()
    auto_recovery = auto_recover_existing_requests()
    result = process_next_queued_task_real(**active_project_task_filter())
    result["stale_cleanup"] = stale_cleanup
    result["auto_recovery"] = auto_recovery

    if result.get("processed") is False:
        message = "No queued tasks to process. No paid generation was started."
    elif result.get("status") == "completed":
        message = f"Queue task #{result.get('task_id')} completed and video was downloaded."
    else:
        message = f"Queue task #{result.get('task_id')} failed. See run folder for details."

    return redirect_home(message)


@app.post("/draft-task", response_class=HTMLResponse)
async def draft_task(
    request: Request,
    prompt: str = Form(""),
    model: str = Form("seedance-2.0"),
    duration: int = Form(4),
    resolution: str = Form("480p"),
    aspect_ratio: str = Form("16:9"),
    episode_name: str = Form("Episode_01"),
    scene_name: str = Form("Scene_001"),
    seed: int = Form(-1),
    generate_audio: str | None = Form(None),
    return_last_frame: str | None = Form(None),
    reference_files: list[UploadFile] = File(default=[]),
):
    model = normalize_model(model)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    draft_dir = projects_module.get_active_project_dir() / "gui_drafts" / f"draft_{timestamp}"
    refs_dir = draft_dir / "refs"

    saved_refs = await save_uploaded_reference_files(reference_files, refs_dir, source="draft_upload")
    prompt = normalize_prompt_reference_tokens(prompt, saved_refs)

    params = build_params(
        model=model,
        prompt=prompt,
        saved_refs=saved_refs,
        duration=duration,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        episode_name=episode_name,
        scene_name=scene_name,
        seed=seed,
        generate_audio=generate_audio,
        return_last_frame=return_last_frame,
        mode="draft_only_no_generation",
    )

    draft_dir.mkdir(parents=True, exist_ok=True)
    (draft_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (draft_dir / "params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")
    (draft_dir / "refs.json").write_text(json.dumps(saved_refs, indent=2, ensure_ascii=False), encoding="utf-8")

    last_draft = {
        "draft_dir": str(draft_dir),
        "model": model,
        "refs_count": len(saved_refs),
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "generate_audio": bool(generate_audio),
        "return_last_frame": bool(return_last_frame),
    }

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message="Draft task saved locally. No paid generation was started.",
            last_draft=last_draft,
        ),
    )



def process_single_generation_task_real(task_id: int) -> None:
    task = get_task(task_id)
    if not task:
        return

    params = task.get("params") or {}
    refs = task.get("refs") or []
    run_dir = Path(task.get("run_dir") or params.get("run_dir"))
    video_path = Path(params.get("video_path") or run_dir / "output.mp4")
    model = task.get("model") or params.get("model") or "seedance-2.0"
    started = time.time()
    request_id = None

    update_task_fields(task_id, status="processing", started_at=datetime.utcnow().isoformat(timespec="seconds") + "Z", run_dir=str(run_dir), error=None)

    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        video_path.parent.mkdir(parents=True, exist_ok=True)
        refs_for_api = [item for item in refs if item.get("media_type") in (None, "image")]
        unsupported_refs = [item for item in refs if item.get("media_type") not in (None, "image")]
        client = SegmindClient(model=model, timeout=600.0)
        uploaded_reference_urls = []
        refs_for_save = []

        for index, item in enumerate(refs_for_api, start=1):
            local_path = item.get("local_path")
            if not local_path:
                continue
            upload_response = client.upload_asset(local_path)
            safe_role = str(item.get("role", f"reference_{index}")).replace(" ", "_")
            (run_dir / f"upload_response_{safe_role}.json").write_text(json.dumps(upload_response.data, indent=2, ensure_ascii=False), encoding="utf-8")
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
            prompt=task.get("prompt") or params.get("prompt") or "",
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

        params_for_save = dict(params)
        params_for_save.update(payload)
        params_for_save["mode"] = params.get("mode", "single_generation_paid")
        params_for_save["reference_images"] = [
            {"local_path": item.get("local_path"), "uploaded_url_present": item.get("uploaded_url_present", False)}
            for item in refs_for_save
        ]
        params_for_save["stored_reference_videos"] = [item["local_path"] for item in unsupported_refs if item.get("media_type") == "video"]
        params_for_save["stored_reference_audios"] = [item["local_path"] for item in unsupported_refs if item.get("media_type") == "audio"]
        params_for_save["video_audio_submission_status"] = "parked_for_later_api_client_step" if unsupported_refs else "not_applicable"

        (run_dir / "prompt.txt").write_text(task.get("prompt") or "", encoding="utf-8")
        (run_dir / "params.json").write_text(json.dumps(params_for_save, indent=2, ensure_ascii=False), encoding="utf-8")
        (run_dir / "refs.json").write_text(json.dumps(refs, indent=2, ensure_ascii=False), encoding="utf-8")

        submit_response = client.submit_seedance_async(payload)
        (run_dir / "submit_response.json").write_text(json.dumps(submit_response.data, indent=2, ensure_ascii=False), encoding="utf-8")
        if not submit_response.ok:
            raise RuntimeError(f"Submit failed with status {submit_response.status_code}: {submit_response.text_preview}")

        request_id = client.extract_request_id(submit_response)
        if not request_id:
            raise RuntimeError("Submit succeeded, but request_id was not found.")
        update_task_fields(task_id, request_id=request_id)

        transient_404_count = 0
        transient_network_error_count = 0
        while True:
            try:
                status_response = client.get_request_status(request_id)
                status = client.extract_status(status_response)
                transient_network_error_count = 0
            except Exception as exc:
                transient_network_error_count += 1
                if transient_network_error_count <= 30:
                    time.sleep(10)
                    continue
                raise RuntimeError(f"Polling did not recover after repeated network errors: {type(exc).__name__}: {exc}")

            (run_dir / "last_status.json").write_text(json.dumps(status_response.data, indent=2, ensure_ascii=False), encoding="utf-8")
            if status_response.status_code == 404:
                transient_404_count += 1
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

        result_response = client.get_request_result(request_id)
        (run_dir / "result_response.json").write_text(json.dumps(result_response.data, indent=2, ensure_ascii=False), encoding="utf-8")
        if not result_response.ok:
            raise RuntimeError(f"Result fetch failed with status {result_response.status_code}: {result_response.text_preview}")

        video_url = extract_output_url(result_response.data)
        if not video_url:
            raise RuntimeError("No video URL found in result response.")

        download_file(video_url, video_path)
        shutil.copy2(video_path, run_dir / "output.mp4")
        last_frame_info = _save_api_last_frame_if_present(result_response.data, run_dir)
        elapsed_total_seconds = int(time.time() - started)
        inference_time = None
        metrics = result_response.data.get("metrics") if isinstance(result_response.data, dict) else None
        if isinstance(metrics, dict):
            inference_time = metrics.get("inference_time")

        summary = {
            "request_id": request_id,
            "model": model,
            "status": "completed",
            "elapsed_total_seconds": elapsed_total_seconds,
            "inference_time": inference_time,
            "video_path": str(video_path),
            "video_size_bytes": video_path.stat().st_size,
            "single_generation_name": params.get("single_generation_name"),
            "task_id": task_id,
            "cost_info": build_cost_info(result_response.data, model=model, duration=params.get("duration"), resolution=params.get("resolution"), aspect_ratio=params.get("aspect_ratio"), refs=refs),
            **last_frame_info,
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        update_task_fields(
            task_id,
            status="completed",
            completed_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            elapsed_total_seconds=elapsed_total_seconds,
            inference_time=inference_time,
            output_path=str(video_path),
            error=None,
        )
    except Exception as exc:
        elapsed_total_seconds = int(time.time() - started)
        error_text = str(exc)
        (run_dir / "errors.log").write_text(json.dumps({"status": "failed", "error_type": type(exc).__name__, "error": error_text, "elapsed_total_seconds": elapsed_total_seconds}, indent=2, ensure_ascii=False), encoding="utf-8")
        update_task_fields(
            task_id,
            status="recoverable" if request_id else "failed",
            completed_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            elapsed_total_seconds=elapsed_total_seconds,
            run_dir=str(run_dir),
            error=error_text,
        )


@app.post("/run-single-generation", response_class=HTMLResponse)
async def run_single_generation(
    request: Request,
    prompt: str = Form(""),
    generation_name: str = Form(""),
    model: str = Form("seedance-2.0"),
    duration: int = Form(4),
    resolution: str = Form("480p"),
    aspect_ratio: str = Form("16:9"),
    seed: int = Form(-1),
    generate_audio: str | None = Form(None),
    return_last_frame: str | None = Form(None),
    reference_files: list[UploadFile] = File(default=[]),
    existing_reference_paths: list[str] = Form(default=[]),
):
    model = normalize_model(model)
    safe_name = normalize_single_generation_name(generation_name)
    episode_name = safe_name
    scene_name = "Single_Generation"
    take_paths = allocate_take_paths(
        project_name=projects_module.get_active_project_name(),
        episode_name=episode_name,
        scene_name=scene_name,
    )
    run_dir = Path(take_paths["run_dir"])
    refs_dir = run_dir / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)

    saved_refs = safe_existing_reference_refs(existing_reference_paths)
    saved_refs.extend(await save_uploaded_reference_files(reference_files, refs_dir, source="single_generation_upload"))
    prompt = normalize_prompt_reference_tokens(prompt, saved_refs)

    params = {
        "project_name": projects_module.get_active_project_name(),
        "project_dir": str(projects_module.get_active_project_dir()),
        "single_generation_name": safe_name,
        "name": safe_name,
        "episode_name": episode_name,
        "scene_name": scene_name,
        "take_number": take_paths["take_number"],
        "take_stem": take_paths["take_stem"],
        "run_dir": take_paths["run_dir"],
        "video_path": take_paths["video_path"],
        "model": model,
        "prompt": prompt,
        "reference_images": [item["local_path"] for item in saved_refs if item.get("media_type") in (None, "image")],
        "reference_videos": [item["local_path"] for item in saved_refs if item.get("media_type") == "video"],
        "reference_audios": [item["local_path"] for item in saved_refs if item.get("media_type") == "audio"],
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "generate_audio": bool(generate_audio),
        "seed": seed,
        "return_last_frame": bool(return_last_frame),
        "skip_moderation": False,
        "mode": "single_generation_paid",
    }

    task_id = create_task(model=model, prompt=prompt, params=params, refs=saved_refs, status="queued")
    update_task_fields(task_id, run_dir=str(run_dir), error=None)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (run_dir / "params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "refs.json").write_text(json.dumps(saved_refs, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "task_id.txt").write_text(str(task_id), encoding="utf-8")

    thread = threading.Thread(target=process_queued_task_real_by_id, args=(task_id,), daemon=True)
    thread.start()

    last_run = {
        "status": "processing",
        "run_dir": str(run_dir),
        "model": model,
        "name": safe_name,
        "elapsed_total_seconds": 0,
        "task_id": task_id,
    }

    return redirect_home(f"Single generation #{task_id} started. It will appear in History while processing.")


@app.post("/retry-task/{task_id}", response_class=HTMLResponse)
def retry_task(task_id: int, request: Request):
    original = get_task(task_id)

    if not original:
        message = f"Task #{task_id} was not found. No new paid submit was started."
        return templates.TemplateResponse(
            "index.html",
            base_context(request, message=message),
            status_code=404,
        )

    if original.get("status") not in ["failed", "recoverable"]:
        message = f"Task #{task_id} is not failed/recoverable, so it was not retried. No new paid submit was started."
        return templates.TemplateResponse(
            "index.html",
            base_context(request, message=message),
        )

    params = dict(original.get("params") or {})
    params["mode"] = "retry_queued_no_generation_yet"
    params["retry_of_task_id"] = task_id

    new_task_id = create_task(
        model=original.get("model"),
        prompt=original.get("prompt"),
        params=params,
        refs=original.get("refs") or [],
        status="queued",
    )

    message = (
        f"Task #{task_id} copied to queue as task #{new_task_id}. "
        "No new paid submit was started."
    )

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=message,
            last_queue_add={
                "task_id": new_task_id,
                "status": "queued",
                "model": original.get("model"),
                "duration": params.get("duration"),
                "resolution": params.get("resolution"),
                "aspect_ratio": params.get("aspect_ratio"),
                "refs_count": len(original.get("refs") or []),
                "task_dir": "created_from_retry_endpoint",
            },
        ),
    )


@app.post("/recover-task/{task_id}", response_class=HTMLResponse)
def recover_task(task_id: int, request: Request):
    result = recover_task_by_existing_request(task_id)

    if result.get("status") == "completed":
        message = f"Task #{task_id} recovered and output video was downloaded. No new paid submit was started."
    elif result.get("reason") == "no_request_id":
        message = f"Task #{task_id} has no request_id, so it cannot be recovered. No new paid submit was started."
    elif result.get("reason") == "task_not_found":
        message = f"Task #{task_id} was not found."
    else:
        message = f"Task #{task_id} recovery did not complete. Reason: {result.get('reason')}. No new paid submit was started."

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=message,
            last_queue_run=result,
        ),
    )


def run_queue_loop_background(*, project_filter: dict, max_tasks: int, stale_cleanup: dict, auto_recovery: dict) -> None:
    try:
        result = process_queue_loop(
            dry_run=False,
            max_tasks=max_tasks,
            stop_on_failure=True,
            **project_filter,
        )
        result["auto_recovery"] = auto_recovery
        result["stale_cleanup"] = stale_cleanup
        mark_queue_loop_finished(result=result)
    except Exception as exc:
        mark_queue_loop_finished(error=str(exc))


@app.post("/stop-queue-loop", response_class=HTMLResponse)
def stop_queue_loop(request: Request):
    paused_task_ids = pause_active_project_queued_tasks()
    mark_queue_loop_stop_requested(paused_count=len(paused_task_ids))

    processing_count = len([task for task in active_project_tasks(limit=1000) if task.get("status") == "processing"])
    if processing_count:
        message = (
            f"Stop requested. Paused {len(paused_task_ids)} queued task(s). "
            "The current processing task cannot be cancelled locally and will finish or fail before the loop stops."
        )
    else:
        message = f"Stop requested. Paused {len(paused_task_ids)} queued task(s)."

    return redirect_home(message)


@app.post("/resume-paused-queue", response_class=HTMLResponse)
def resume_paused_queue(request: Request):
    resumed_task_ids = resume_active_project_paused_tasks()
    message = f"Resumed {len(resumed_task_ids)} paused queue task(s)."
    return redirect_home(message)


@app.post("/start-queue-loop", response_class=HTMLResponse)
def start_queue_loop(
    request: Request,
    max_tasks: int = Form(50),
):
    if max_tasks < 1:
        max_tasks = 1

    if max_tasks > 50:
        max_tasks = 50

    project_filter = active_project_task_filter()
    current_state = queue_loop_state_snapshot()
    if current_state.get("active"):
        active_project = current_state.get("project_name") or "another project"
        message = f"Queue loop is already running for {active_project}. Wait for it to finish before starting another paid run."
        return redirect_home(message)

    stale_cleanup = cleanup_processing_without_request_id()
    auto_recovery = auto_recover_existing_requests()
    mark_queue_loop_started(
        project_name=project_filter["project_name"],
        project_dir=project_filter["project_dir"],
        max_tasks=max_tasks,
    )

    thread = threading.Thread(
        target=run_queue_loop_background,
        kwargs={
            "project_filter": project_filter,
            "max_tasks": max_tasks,
            "stale_cleanup": stale_cleanup,
            "auto_recovery": auto_recovery,
        },
        daemon=True,
    )
    thread.start()

    message = f"Queue loop started in background for up to {max_tasks} task(s). This page refreshes automatically."

    return redirect_home(message)


@app.get("/open-path", response_class=HTMLResponse)
def open_path(path: str):
    output_root = projects_module.get_output_root().resolve()
    target = Path(path).resolve()

    try:
        is_allowed = target == output_root or output_root in target.parents
    except RuntimeError:
        is_allowed = False

    if not is_allowed:
        return HTMLResponse(
            "<h3>Blocked</h3><p>Path is outside the configured output folder.</p>",
            status_code=400,
        )

    if not target.exists():
        return HTMLResponse(
            f"<h3>Not found</h3><p>{target}</p>",
            status_code=404,
        )

    if target.is_file():
        windows_target = to_windows_path(str(target))
        subprocess.Popen(["explorer.exe", "/select,", windows_target])
        opened_text = f"Opened folder and selected file: {windows_target}"
    else:
        windows_target = to_windows_path(str(target))
        subprocess.Popen(["explorer.exe", windows_target])
        opened_text = f"Opened folder: {windows_target}"

    return HTMLResponse(
        f"""
        <!doctype html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Opened path</title>
        </head>
        <body style="font-family: sans-serif; background: #111; color: #eee;">
          <h3>Windows Explorer command sent</h3>
          <p>{opened_text}</p>
          <p>You can close this tab.</p>
        </body>
        </html>
        """
    )


@app.get("/health")
def health():
    return {
        "ok": True,
        "stage": "product_ui",
        "api_key_set": bool(SEGMIND_API_KEY),
        "default_model": SEGMIND_MODEL,
        "available_models": [item["id"] for item in MODEL_CHOICES],
        "output_dir": str(projects_module.get_active_project_dir()),
        "queue_tasks_count": len(active_project_tasks(limit=1000)),
    }



@app.post("/continue-from-task/{task_id}", response_class=HTMLResponse)
def continue_from_task(request: Request, task_id: int):
    parent_task = get_task(task_id)

    if not parent_task:
        return templates.TemplateResponse(
            "index.html",
            base_context(request, message=f"Parent task #{task_id} was not found."),
        )

    if parent_task.get("status") != "completed":
        return templates.TemplateResponse(
            "index.html",
            base_context(request, message=f"Parent task #{task_id} is not completed yet."),
        )

    frame_info = last_frame_view_for_task(parent_task)

    if not frame_info.get("last_frame_exists"):
        return templates.TemplateResponse(
            "index.html",
            base_context(request, message=f"Parent task #{task_id} has no saved last_frame.png."),
        )

    parent_params = parent_task.get("params") or {}
    parent_refs = parent_task.get("refs") or []

    parent_project_name = parent_params.get("project_name") or projects_module.get_active_project_name()
    parent_project_dir = parent_params.get("project_dir") or str(projects_module.get_active_project_dir())

    parent_last_frame_path = frame_info["last_frame_path"]
    parent_output_path = parent_task.get("output_path")

    parent_take_stem = None
    if parent_output_path:
        parent_take_stem = Path(parent_output_path).stem
    elif parent_task.get("run_dir"):
        parent_take_stem = Path(parent_task["run_dir"]).name

    continuation_index = int(parent_params.get("continuation_index") or 0) + 1

    base_prompt = (parent_task.get("prompt") or "").strip()
    continuation_note = (
        "Continue this scene naturally from the previous clip. "
        "Use the previous clip final frame as a visual reference, not as a strict first frame."
    )

    if continuation_note not in base_prompt:
        new_prompt = base_prompt + "\n\n" + continuation_note if base_prompt else continuation_note
    else:
        new_prompt = base_prompt

    refs = list(parent_refs)
    refs.append(
        {
            "role": "parent_last_frame_reference",
            "local_path": parent_last_frame_path,
            "source": "continue_from_previous_take",
            "parent_task_id": task_id,
            "parent_take_stem": parent_take_stem,
        }
    )

    params = dict(parent_params)
    params.update(
        {
            "project_name": parent_project_name,
            "project_dir": parent_project_dir,
            "episode_name": parent_params.get("episode_name") or "Episode_01",
            "scene_name": parent_params.get("scene_name") or "Scene_001",
            "model": "seedance-2.0-fast",
            "reference_images": [item.get("local_path") for item in refs if item.get("local_path")],
            "reference_videos": [],
            "reference_audios": [],
            "duration": int(parent_params.get("duration", 4)),
            "resolution": str(parent_params.get("resolution", "480p")),
            "aspect_ratio": str(parent_params.get("aspect_ratio", "16:9")),
            "generate_audio": bool(parent_params.get("generate_audio", False)),
            "seed": -1,
            "return_last_frame": True,
            "skip_moderation": False,
            "mode": "continuation_queued_no_generation_yet",
            "continuation_mode": "last_frame_as_reference",
            "parent_task_id": task_id,
            "parent_take_stem": parent_take_stem,
            "parent_video_path": parent_output_path,
            "parent_last_frame_path": parent_last_frame_path,
            "continuation_index": continuation_index,
        }
    )

    new_task_id = create_task(
        model="seedance-2.0-fast",
        prompt=new_prompt,
        params=params,
        refs=refs,
        status="queued",
    )

    queue_task_dir = Path(parent_project_dir) / "queue_tasks" / f"task_{new_task_id:06d}"
    queue_task_dir.mkdir(parents=True, exist_ok=True)

    (queue_task_dir / "prompt.txt").write_text(new_prompt, encoding="utf-8")
    (queue_task_dir / "params.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")
    (queue_task_dir / "refs.json").write_text(json.dumps(refs, indent=2, ensure_ascii=False), encoding="utf-8")
    (queue_task_dir / "task_id.txt").write_text(str(new_task_id), encoding="utf-8")

    message = (
        f"Continuation task #{new_task_id} was added to queue from task #{task_id}. "
        "No paid generation was started. The parent last_frame.png will be used as a reference image."
    )

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=message,
            last_queue_add={
                "task_id": new_task_id,
                "status": "queued",
                "model": "seedance-2.0-fast",
                "duration": params["duration"],
                "resolution": params["resolution"],
                "aspect_ratio": params["aspect_ratio"],
                "refs_count": len(refs),
                "task_dir": str(queue_task_dir),
            },
        ),
    )


@app.get("/safe-media-file")
def safe_media_file(path: str):
    output_root = projects_module.get_output_root().resolve()

    try:
        requested = Path(path).resolve()
    except Exception:
        return HTMLResponse("Invalid file path.", status_code=400)

    if not requested.exists() or not requested.is_file():
        return HTMLResponse("File not found.", status_code=404)

    try:
        if not requested.is_relative_to(output_root):
            return HTMLResponse("File is outside output root.", status_code=403)
    except Exception:
        return HTMLResponse("File is outside output root.", status_code=403)

    allowed_suffixes = REFERENCE_FILE_SUFFIXES | {".mp4"}
    if requested.suffix.lower() not in allowed_suffixes:
        return HTMLResponse("Unsupported file type.", status_code=415)

    return FileResponse(requested)
