from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

import app.main as main
from app.db import list_tasks


def main_run() -> int:
    print("=== Stage 8 GUI last-frame preview check ===")

    tasks = list_tasks(limit=1000)
    task_with_frame = None
    last_frame_path = None

    for task in tasks:
        run_dir = task.get("run_dir")
        output_path = task.get("output_path")

        candidates = []

        if run_dir:
            candidates.append(Path(run_dir) / "last_frame.png")

        if output_path:
            output = Path(output_path)
            if output.parent.name == "videos":
                candidates.append(output.parent.parent / "runs" / output.stem / "last_frame.png")

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                task_with_frame = task
                last_frame_path = candidate
                break

        if task_with_frame:
            break

    print("task_with_last_frame_found=", task_with_frame is not None, sep="")

    if task_with_frame:
        print("task_id=", task_with_frame.get("id"), sep="")
        print("last_frame_path=", last_frame_path, sep="")
        print("last_frame_size=", last_frame_path.stat().st_size, sep="")

    client = TestClient(main.app)

    index_response = client.get("/")
    print("index_status_code=", index_response.status_code, sep="")
    text = index_response.text

    contains_last_frame_label = "Last frame:" in text
    contains_last_frame_preview = "last-frame-preview" in text
    contains_media_file_route = "/media-file?path=" in text

    print("contains_last_frame_label=", contains_last_frame_label, sep="")
    print("contains_last_frame_preview=", contains_last_frame_preview, sep="")
    print("contains_media_file_route=", contains_media_file_route, sep="")

    media_status_ok = False

    if last_frame_path:
        media_response = client.get("/media-file", params={"path": str(last_frame_path)})
        print("media_status_code=", media_response.status_code, sep="")
        print("media_content_type=", media_response.headers.get("content-type"), sep="")
        print("media_size=", len(media_response.content), sep="")
        media_status_ok = media_response.status_code == 200 and len(media_response.content) > 0
    else:
        print("media_status_code=None")
        print("media_content_type=None")
        print("media_size=0")

    print("new_paid_submit_started=False")

    ok = (
        task_with_frame is not None
        and index_response.status_code == 200
        and contains_last_frame_label
        and contains_last_frame_preview
        and contains_media_file_route
        and media_status_ok
    )

    if ok:
        print("RESULT=STAGE8_GUI_LAST_FRAME_PREVIEW_OK")
        return 0

    print("RESULT=STAGE8_GUI_LAST_FRAME_PREVIEW_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
