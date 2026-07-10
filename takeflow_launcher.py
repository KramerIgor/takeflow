from __future__ import annotations

import os
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

import httpx
import uvicorn


LOG_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "Takeflow" / "logs"
LOG_PATH = LOG_DIR / "launcher.log"


def log_launcher(message: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as log_file:
            timestamp = datetime.now().isoformat(timespec="seconds")
            log_file.write(f"[{timestamp}] {message}\n")
    except OSError:
        pass


log_launcher("Launcher process started.")
try:
    from app.main import app
except Exception:
    log_launcher(f"Backend import failed:\n{traceback.format_exc()}")
    raise
else:
    log_launcher("Backend import completed.")


HOST = os.getenv("TAKEFLOW_HOST", "127.0.0.1")
PORT = int(os.getenv("TAKEFLOW_PORT", "7860"))
URL = f"http://{HOST}:{PORT}"
OPEN_BROWSER = os.getenv("TAKEFLOW_OPEN_BROWSER", "1").strip().lower() not in {"0", "false", "no"}


def open_browser_when_ready() -> None:
    if not OPEN_BROWSER:
        return

    health_url = f"{URL}/health"
    for _ in range(80):
        try:
            response = httpx.get(health_url, timeout=0.25)
            if response.status_code == 200:
                webbrowser.open(URL)
                return
        except Exception:
            pass
        time.sleep(0.25)


def main() -> int:
    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    log_launcher(f"Starting local server at {URL}.")
    try:
        uvicorn.run(
            app,
            host=HOST,
            port=PORT,
            log_level=os.getenv("TAKEFLOW_LOG_LEVEL", "warning"),
            access_log=False,
            log_config=None,
        )
    except Exception:
        log_launcher(f"Local server failed:\n{traceback.format_exc()}")
        raise
    finally:
        log_launcher("Local server stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
