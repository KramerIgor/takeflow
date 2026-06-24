from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import unicodedata

from app.db import DATA_DIR
from app.settings import OUTPUT_DIR


WINDOWS_FORBIDDEN_CHARS = '<>:"/\\|?*'
RESERVED_NAMES = {".", ".."}
ACTIVE_PROJECT_FILE = DATA_DIR / "active_project.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_output_root() -> Path:
    explicit_root = os.getenv("OUTPUT_ROOT", "").strip()

    if explicit_root:
        return Path(explicit_root)

    return Path(OUTPUT_DIR).parent


def get_default_project_name() -> str:
    return Path(OUTPUT_DIR).name


def sanitize_project_name(project_name: str) -> str:
    name = unicodedata.normalize("NFKC", project_name or "").strip()

    for char in WINDOWS_FORBIDDEN_CHARS:
        name = name.replace(char, "_")

    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip(" .")

    if not name or name in RESERVED_NAMES:
        raise ValueError("Project name is empty or invalid after sanitizing.")

    return name[:80]


def get_project_dir(project_name: str, root: Path | None = None) -> Path:
    base = Path(root) if root is not None else get_output_root()
    safe_name = sanitize_project_name(project_name)
    return base / safe_name


def create_project(project_name: str, root: Path | None = None) -> Path:
    project_dir = get_project_dir(project_name, root=root)
    (project_dir / "results" / "_inbox").mkdir(parents=True, exist_ok=True)
    return project_dir


def read_active_project_state() -> dict:
    if not ACTIVE_PROJECT_FILE.exists():
        return {}

    try:
        data = json.loads(ACTIVE_PROJECT_FILE.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            return {}

        return data

    except Exception:
        return {}


def get_active_project_name() -> str:
    state = read_active_project_state()
    raw_name = str(state.get("active_project_name") or "").strip()

    if raw_name:
        try:
            return sanitize_project_name(raw_name)
        except ValueError:
            pass

    return get_default_project_name()


def get_active_project_dir() -> Path:
    return get_project_dir(get_active_project_name())


def set_active_project(project_name: str) -> dict:
    safe_name = sanitize_project_name(project_name)
    project_dir = create_project(safe_name)

    ACTIVE_PROJECT_FILE.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "active_project_name": safe_name,
        "active_project_dir": str(project_dir),
        "output_root": str(get_output_root()),
        "updated_at": utc_now(),
    }

    ACTIVE_PROJECT_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return state


def list_projects(root: Path | None = None) -> list[dict]:
    base = Path(root) if root is not None else get_output_root()
    base.mkdir(parents=True, exist_ok=True)

    active_name = get_active_project_name()
    projects = []

    for item in sorted(base.iterdir(), key=lambda path: path.name.lower()):
        if not item.is_dir():
            continue

        projects.append(
            {
                "name": item.name,
                "path": str(item),
                "is_active": item.name == active_name,
                "has_results": (item / "results").exists(),
                "has_inbox": (item / "results" / "_inbox").exists(),
            }
        )

    return projects
