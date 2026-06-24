from pathlib import Path
from dotenv import load_dotenv
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)

SEGMIND_API_KEY = os.getenv("SEGMIND_API_KEY", "")
SEGMIND_MODEL = os.getenv("SEGMIND_MODEL", "seedance-2.0")
SEGMIND_API_BASE = os.getenv("SEGMIND_API_BASE", "https://api.segmind.com")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/mnt/c/AI_OUTPUT/Psailor_kun"))
