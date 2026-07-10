from __future__ import annotations

from pathlib import Path
import os
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IS_MACOS = sys.platform == "darwin"


def app_support_dir() -> Path:
    override = os.getenv("TAKEFLOW_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if IS_MACOS:
        return Path.home() / "Library" / "Application Support" / "Takeflow"
    return PROJECT_ROOT / "data"


def environment_path() -> Path:
    override = os.getenv("TAKEFLOW_ENV_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    if IS_MACOS:
        return app_support_dir() / ".env"
    return PROJECT_ROOT / ".env"


def launcher_log_dir() -> Path:
    override = os.getenv("TAKEFLOW_LOG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if IS_MACOS:
        return Path.home() / "Library" / "Logs" / "Takeflow"
    return Path(os.getenv("LOCALAPPDATA", Path.home())) / "Takeflow" / "logs"


def default_output_dir() -> Path:
    if IS_MACOS:
        return Path.home() / "Movies" / "Takeflow" / "Example_project"
    return Path("/mnt/c/AI_OUTPUT/Psailor_kun")


DATA_DIR = app_support_dir()
ENV_PATH = environment_path()
UPDATE_DIR = DATA_DIR / "updates"
