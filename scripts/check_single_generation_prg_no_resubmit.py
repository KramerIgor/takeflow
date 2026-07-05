from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

import app.main as main


class FakeThread:
    started = 0

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def start(self):
        FakeThread.started += 1


def main_check() -> None:
    original_allocate_take_paths = main.allocate_take_paths
    original_create_task = main.create_task
    original_update_task_fields = main.update_task_fields
    original_thread = main.threading.Thread

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_dir = tmp_path / "runs" / "single_prg_check"
        video_path = tmp_path / "videos" / "single_prg_check.mp4"

        def fake_allocate_take_paths(**kwargs):
            return {
                "run_dir": str(run_dir),
                "video_path": str(video_path),
                "take_number": 1,
                "take_stem": "single_prg_check",
            }

        try:
            main.allocate_take_paths = fake_allocate_take_paths
            main.create_task = lambda **kwargs: 999001
            main.update_task_fields = lambda *args, **kwargs: None
            main.threading.Thread = FakeThread
            FakeThread.started = 0

            client = TestClient(main.app)
            response = client.post(
                "/run-single-generation",
                data={
                    "prompt": "PRG regression check",
                    "generation_name": "prg-check",
                    "model": "seedance-2.0",
                    "duration": "4",
                    "resolution": "480p",
                    "aspect_ratio": "16:9",
                    "seed": "-1",
                },
                follow_redirects=False,
            )

            assert response.status_code == 303, response.status_code
            assert response.headers["location"].startswith("/?message="), response.headers.get("location")
            assert FakeThread.started == 1, FakeThread.started
            print("SINGLE_GENERATION_PRG_OK")
        finally:
            main.allocate_take_paths = original_allocate_take_paths
            main.create_task = original_create_task
            main.update_task_fields = original_update_task_fields
            main.threading.Thread = original_thread


if __name__ == "__main__":
    main_check()
