from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import csv
import json
import os
import shutil
import subprocess
import threading
import time
import uuid

import httpx
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import create_task, get_task, init_db, list_tasks, update_task_fields
from app.queue_worker import process_next_queued_task_real, process_queue_loop, _save_api_last_frame_if_present
from app.settings import ENV_PATH, OUTPUT_DIR, SEGMIND_API_KEY, SEGMIND_API_BASE, SEGMIND_MODEL
from app.segmind_client import SegmindClient
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

DURATIONS = [4, 5, 6, 8, 10, 12, 15]
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


def extract_cost_info(data: dict | None) -> dict | None:
    if not isinstance(data, dict):
        return None

    candidates = []

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = str(key).lower()
                next_path = f"{path}.{key}" if path else str(key)
                if any(token in key_lower for token in ("cost", "price", "credit", "billing", "amount")):
                    if isinstance(value, (int, float, str)):
                        candidates.append({"key": next_path, "value": value})
                    elif isinstance(value, dict):
                        candidates.append({"key": next_path, "value": value})
                walk(value, next_path)
        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                walk(value, f"{path}[{index}]")

    walk(data)
    if not candidates:
        return None

    return {"source": "segmind_response", "items": candidates[:8]}


def cost_label_from_summary(summary: dict | None) -> str | None:
    if not isinstance(summary, dict):
        return None
    cost_info = summary.get("cost_info")
    if not isinstance(cost_info, dict):
        return None
    items = cost_info.get("items") or []
    if not items:
        return None
    first = items[0]
    value = first.get("value")
    key = first.get("key") or "cost"
    return f"{key}: {value}"


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
            exists = path.exists() and path.is_file() and path.is_relative_to(output_root)
            if exists and media_type in {"image", "video", "audio"}:
                preview_url = "/safe-media-file?path=" + quote(str(path), safe="")
                local_path = str(path)
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
    for task in list_tasks(limit=10000):
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
    tasks = []
    for task in list_tasks(limit=200):
        params = task.get("params") or {}
        if params.get("mode") in SINGLE_GENERATION_MODES:
            continue
        tasks.append(task)
        if len(tasks) >= 20:
            break

    for task in tasks:
        output_path = task.get("output_path")
        params = task.get("params") or {}

        task["output_windows_path"] = to_windows_path(output_path)
        task["output_filename"] = Path(output_path).name if output_path else None
        task["run_dir_windows_path"] = to_windows_path(task.get("run_dir"))
        task["batch_row_number"] = params.get("batch_row_number")
        task["batch_import_id"] = params.get("batch_import_id")
        task["task_mode"] = params.get("mode")
        task["is_batch_import"] = bool(params.get("batch_import_id") or params.get("batch_row_number"))
        task.update(last_frame_view_for_task(task))

    return tasks


def safe_existing_reference_refs(reference_paths: list[str]) -> list[dict]:
    refs = []
    output_root = projects_module.get_output_root().resolve()

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
            if not resolved.exists() or not resolved.is_file() or not resolved.is_relative_to(output_root):
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

    return {
        "source": "db",
        "task_id": task.get("id"),
        "status": task.get("status"),
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
        "cost_label": cost_label_from_summary(summary),
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
        cost_label = cost_label_from_summary(summary)

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

    for task in list_tasks(limit=1000):
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
    context = {
        "request": request,
        "app_version": "0.1.0",
        "app_title": APP_TITLE,
        "app_subtitle": APP_SUBTITLE,
        "api_key_set": env_key_is_set(),
        "api_base": SEGMIND_API_BASE,
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
        "queue_tasks": queue_tasks_for_view(),
        "single_history": single_generation_history_for_view(),
        "has_processing_single_generation": any(item.get("status") in {"queued", "processing"} for item in single_generation_history_for_view(limit=20)),
    }

    context.update(project_context())

    return context

def cleanup_processing_without_request_id(limit: int = 20) -> dict:
    tasks = list_tasks(limit=1000)

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
    tasks = list_tasks(limit=1000)

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
        "reference_images": [item["local_path"] for item in saved_refs],
        "reference_videos": [],
        "reference_audios": [],
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
    lines = (csv_text or "").splitlines()
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

    for row in valid_rows:
        refs = refs_from_reference_paths(row["reference_paths"], row["row_number"])
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

        task_id = create_task_fn(
            model=row["model"],
            prompt=row["prompt"],
            params=params,
            refs=refs,
            status="queued",
        )

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
        tasks = list_tasks(limit=1000)

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


async def save_uploaded_reference_files(reference_files: list[UploadFile], refs_dir: Path) -> list[dict]:
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
                "source": "single_generation_upload",
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
    reference_images: list[UploadFile] = File(default=[]),
):
    model = normalize_model(model)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    queue_dir = projects_module.get_active_project_dir() / "queue_tasks" / f"queued_{timestamp}"
    refs_dir = queue_dir / "refs"
    queue_dir.mkdir(parents=True, exist_ok=True)

    saved_refs = await save_uploaded_refs(reference_images, refs_dir)

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

    task_id = create_task(
        model=model,
        prompt=prompt,
        params=params,
        refs=saved_refs,
        status="queued",
    )

    queue_task_dir = projects_module.get_active_project_dir() / "queue_tasks" / f"task_{task_id:06d}"
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
    reference_images: list[UploadFile] = File(default=[]),
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

    saved_refs = await save_uploaded_refs(reference_images, refs_dir)

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
    result = process_next_queued_task_real()
    result["stale_cleanup"] = stale_cleanup
    result["auto_recovery"] = auto_recovery

    if result.get("processed") is False:
        message = "No queued tasks to process. No paid generation was started."
    elif result.get("status") == "completed":
        message = f"Queue task #{result.get('task_id')} completed and video was downloaded."
    else:
        message = f"Queue task #{result.get('task_id')} failed. See run folder for details."

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=message,
            last_queue_run=result,
        ),
    )


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
    reference_images: list[UploadFile] = File(default=[]),
):
    model = normalize_model(model)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    draft_dir = projects_module.get_active_project_dir() / "gui_drafts" / f"draft_{timestamp}"
    refs_dir = draft_dir / "refs"

    saved_refs = await save_uploaded_refs(reference_images, refs_dir)

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
            "cost_info": extract_cost_info(result_response.data),
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
    saved_refs.extend(await save_uploaded_reference_files(reference_files, refs_dir))

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

    thread = threading.Thread(target=process_single_generation_task_real, args=(task_id,), daemon=True)
    thread.start()

    last_run = {
        "status": "processing",
        "run_dir": str(run_dir),
        "model": model,
        "name": safe_name,
        "elapsed_total_seconds": 0,
        "task_id": task_id,
    }

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=f"Single generation #{task_id} started. It will appear in History while processing.",
            last_run=last_run,
        ),
    )


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


@app.post("/start-queue-loop", response_class=HTMLResponse)
def start_queue_loop(
    request: Request,
    max_tasks: int = Form(2),
):
    if max_tasks < 1:
        max_tasks = 1

    if max_tasks > 20:
        max_tasks = 20

    stale_cleanup = cleanup_processing_without_request_id()
    auto_recovery = auto_recover_existing_requests()

    result = process_queue_loop(
        dry_run=False,
        max_tasks=max_tasks,
        stop_on_failure=True,
    )

    result["auto_recovery"] = auto_recovery
    result["stale_cleanup"] = stale_cleanup

    processed_count = result.get("processed_count", 0)
    completed_count = result.get("completed_count", 0)
    failed_count = result.get("failed_count", 0)
    stopped_reason = result.get("stopped_reason")

    if processed_count == 0:
        recovered_count = result.get("auto_recovery", {}).get("completed_count", 0)

        if recovered_count:
            message = f"Auto-recovered {recovered_count} existing Segmind result(s). No new paid generation was started."
        else:
            message = "No queued tasks to process. No paid generation was started."
    else:
        message = (
            f"Queue loop finished: processed {processed_count}, "
            f"completed {completed_count}, failed {failed_count}."
        )

        if stopped_reason:
            message += f" Stopped reason: {stopped_reason}."

    return templates.TemplateResponse(
        "index.html",
        base_context(
            request,
            message=message,
            last_queue_run=result,
        ),
    )


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
        "queue_tasks_count": len(list_tasks(limit=1000)),
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
