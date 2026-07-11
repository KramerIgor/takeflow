from __future__ import annotations

import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAFE_ROOT = PROJECT_ROOT / "tmp_test_output" / "shutdown_flow"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_page(url: str) -> str:
    deadline = time.time() + 12
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return response.read().decode("utf-8")
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("Temporary Takeflow server did not start")


def main() -> int:
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHON_DOTENV_DISABLED"] = "1"
    env["SEGMIND_API_KEY"] = ""
    env["OUTPUT_ROOT"] = str(SAFE_ROOT)
    env["OUTPUT_DIR"] = str(SAFE_ROOT / "MyFirstProject")
    env["TAKEFLOW_DATA_DIR"] = str(SAFE_ROOT / f"data_{port}")

    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    response_ok = False
    stopped = False
    try:
        page = wait_for_page(url + "/")
        match = re.search(r"shutdownToken:\s*(\"(?:[^\"\\]|\\.)*\")", page)
        if not match:
            raise RuntimeError("Shutdown token was not rendered")
        token = json.loads(match.group(1))
        body = urllib.parse.urlencode({"token": token}).encode("utf-8")
        request = urllib.request.Request(url + "/shutdown", data=body, method="POST")
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
            response_ok = response.status == 200 and payload.get("ok") is True

        process.wait(timeout=6)
        stopped = process.returncode is not None
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    print(f"shutdown_response_ok={response_ok}")
    print(f"server_process_stopped={stopped}")
    print("new_paid_submit_started=False")
    if response_ok and stopped:
        print("RESULT=SHUTDOWN_FLOW_OK")
        return 0
    print("RESULT=SHUTDOWN_FLOW_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
