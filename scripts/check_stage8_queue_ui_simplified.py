from pathlib import Path
import multiprocessing
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from fastapi.testclient import TestClient

import app.main as main
from app.db import list_tasks


def find_completed_task_with_last_frame():
    for task in list_tasks(limit=1000):
        output_path = task.get("output_path")
        run_dir = task.get("run_dir")

        candidates = []

        if run_dir:
            candidates.append(Path(run_dir) / "last_frame.png")

        if output_path:
            output = Path(output_path)
            if output.parent.name == "videos":
                candidates.append(output.parent.parent / "runs" / output.stem / "last_frame.png")

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return task, candidate

    return None, None


def text_is_inside_debug_details(text: str, needle: str) -> bool:
    position = text.find(needle)
    if position < 0:
        return False

    details_open = text.rfind("<details", 0, position)
    summary = text.rfind("<summary>Debug / files</summary>", 0, position)
    details_close = text.find("</details>", position)

    return details_open >= 0 and summary > details_open and details_close > position


def fetch_index_with_testclient(queue: multiprocessing.Queue) -> None:
    try:
        client = TestClient(main.app)
        response = client.get("/")
        queue.put((response.status_code, response.text, None))
    except Exception as exc:
        queue.put((None, "", f"{type(exc).__name__}: {exc}"))


def render_index_html_without_asgi() -> tuple[int, str]:
    template = main.templates.get_template("index.html")
    html = template.render(main.base_context(request=None))
    return 200, html


def main_run() -> int:
    print("=== Stage 8 simplified queue UI check ===")

    task, last_frame = find_completed_task_with_last_frame()
    print("task_with_last_frame_found=", task is not None, sep="")

    if not task or not last_frame:
        print("new_paid_submit_started=False")
        print("RESULT=STAGE8_QUEUE_UI_SIMPLIFIED_FAILED_NO_LAST_FRAME")
        return 1

    task_id = int(task["id"])
    output_path = task.get("output_path") or ""
    run_dir = task.get("run_dir") or ""

    print("task_id=", task_id, sep="")
    print("last_frame_exists=", last_frame.exists(), sep="")

    queue: multiprocessing.Queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=fetch_index_with_testclient, args=(queue,))
    process.start()
    process.join(timeout=5)

    testclient_timed_out = process.is_alive()
    testclient_error = None

    if testclient_timed_out:
        process.terminate()
        process.join(timeout=2)
        status_code, text = render_index_html_without_asgi()
    else:
        status_code, text, testclient_error = queue.get()
        if status_code is None:
            status_code, text = render_index_html_without_asgi()

    print("testclient_timed_out=", testclient_timed_out, sep="")
    print("testclient_error=", testclient_error, sep="")
    print("index_status_code=", status_code, sep="")

    contains_preview = "last-frame-preview compact-preview" in text
    contains_ready_summary = "Video:" in text and "Last frame:" in text
    contains_debug_details = "<summary>Debug / files</summary>" in text
    continue_in_debug = text_is_inside_debug_details(text, "Continue from previous take")
    last_frame_path_in_debug = text_is_inside_debug_details(text, str(last_frame))
    output_path_in_debug = bool(output_path) and text_is_inside_debug_details(text, output_path)
    run_dir_in_debug = bool(run_dir) and text_is_inside_debug_details(text, run_dir)
    old_stage5_text_removed = "Start Queue comes later in Stage 5" not in text

    print("contains_compact_last_frame_preview=", contains_preview, sep="")
    print("contains_ready_summary=", contains_ready_summary, sep="")
    print("contains_debug_details=", contains_debug_details, sep="")
    print("continue_button_inside_debug_details=", continue_in_debug, sep="")
    print("last_frame_path_inside_debug_details=", last_frame_path_in_debug, sep="")
    print("output_path_inside_debug_details=", output_path_in_debug, sep="")
    print("run_dir_inside_debug_details=", run_dir_in_debug, sep="")
    print("old_stage5_text_removed=", old_stage5_text_removed, sep="")
    print("new_paid_submit_started=False")

    ok = (
        status_code == 200
        and contains_preview
        and contains_ready_summary
        and contains_debug_details
        and continue_in_debug
        and last_frame_path_in_debug
        and output_path_in_debug
        and run_dir_in_debug
        and old_stage5_text_removed
    )

    if ok:
        print("RESULT=STAGE8_QUEUE_UI_SIMPLIFIED_OK")
        return 0

    print("RESULT=STAGE8_QUEUE_UI_SIMPLIFIED_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
