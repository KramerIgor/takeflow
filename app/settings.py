from pathlib import Path
from dotenv import load_dotenv
import os

from app.runtime_paths import ENV_PATH, default_output_dir

load_dotenv(ENV_PATH)


def normalize_runtime_path(path_value: str | Path) -> Path:
    text = str(path_value)

    if os.name == "nt" and text.startswith("/mnt/") and len(text) > 6 and text[5].isalpha() and text[6] == "/":
        drive = text[5].upper()
        rest = text[7:].replace("/", "\\")
        return Path(f"{drive}:\\{rest}")

    return Path(text)


SEGMIND_API_KEY = os.getenv("SEGMIND_API_KEY", "")
SEGMIND_MODEL = os.getenv("SEGMIND_MODEL", "seedance-2.0")
SEGMIND_API_BASE = os.getenv("SEGMIND_API_BASE", "https://api.segmind.com")
OUTPUT_DIR = normalize_runtime_path(os.getenv("OUTPUT_DIR", str(default_output_dir())))


def get_segmind_api_key() -> str:
    return os.getenv("SEGMIND_API_KEY", SEGMIND_API_KEY)


def get_segmind_api_base() -> str:
    return os.getenv("SEGMIND_API_BASE", SEGMIND_API_BASE)


def apply_runtime_segmind_settings(*, api_key: str, api_base: str) -> None:
    global SEGMIND_API_KEY, SEGMIND_API_BASE

    SEGMIND_API_KEY = api_key
    SEGMIND_API_BASE = api_base.rstrip("/")
    os.environ["SEGMIND_API_KEY"] = SEGMIND_API_KEY
    os.environ["SEGMIND_API_BASE"] = SEGMIND_API_BASE
