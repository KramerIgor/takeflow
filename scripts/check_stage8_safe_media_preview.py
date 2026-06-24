from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

import app.main as main
from app.db import list_tasks


def find_last_frame():
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


def main_run():
    print("=== Stage 8 safe media preview check ===")

    task, last_frame = find_last_frame()

    print("last_frame_found=", last_frame is not None, sep="")

    if last_frame:
        print("task_id=", task.get("id"), sep="")
        print("last_frame_path=", last_frame, sep="")
        print("last_frame_size=", last_frame.stat().st_size, sep="")

    client = TestClient(main.app)

    route_paths = sorted(route.path for route in main.app.routes)
    print("safe_media_route_registered=", "/safe-media-file" in route_paths, sep="")

    index_response = client.get("/")
    print("index_status_code=", index_response.status_code, sep="")

    index_text = index_response.text
    print("index_contains_last_frame_label=", "Last frame:" in index_text, sep="")
    print("index_contains_safe_media_route=", "/safe-media-file?path=" in index_text, sep="")

    media_ok = False

    if last_frame:
        media_response = client.get("/safe-media-file", params={"path": str(last_frame)})
        print("safe_media_status_code=", media_response.status_code, sep="")
        print("safe_media_content_type=", media_response.headers.get("content-type"), sep="")
        print("safe_media_size=", len(media_response.content), sep="")
        media_ok = media_response.status_code == 200 and len(media_response.content) > 0
    else:
        print("safe_media_status_code=None")
        print("safe_media_content_type=None")
        print("safe_media_size=0")

    print("new_paid_submit_started=False")

    ok = (
        last_frame is not None
        and "/safe-media-file" in route_paths
        and index_response.status_code == 200
        and "Last frame:" in index_text
        and "/safe-media-file?path=" in index_text
        and media_ok
    )

    if ok:
        print("RESULT=STAGE8_SAFE_MEDIA_PREVIEW_OK")
        return 0

    print("RESULT=STAGE8_SAFE_MEDIA_PREVIEW_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
