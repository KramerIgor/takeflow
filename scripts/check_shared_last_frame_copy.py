from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.queue_worker as queue_worker


def main() -> int:
    original_download = queue_worker._download_file

    with TemporaryDirectory() as tmp:
        project_dir = Path(tmp) / "Project_A"
        run_dir = project_dir / "runs" / "Episode_01_Scene_003_take_000007"
        run_dir.mkdir(parents=True)

        def fake_download(url: str, path: Path) -> None:
            path.write_bytes(b"fake-last-frame")

        queue_worker._download_file = fake_download
        try:
            info = queue_worker._save_api_last_frame_if_present(
                {
                    "video": {
                        "last_frame_url": "https://example.test/last-frame.png",
                    }
                },
                run_dir,
            )
        finally:
            queue_worker._download_file = original_download

        run_last_frame = run_dir / "last_frame.png"
        shared_last_frame = project_dir / "last_frames" / "Episode_01_Scene_003_take_000007_last_frame.png"

        checks = {
            "found": info.get("last_frame_found") is True,
            "run_last_frame_exists": run_last_frame.exists(),
            "shared_last_frame_exists": shared_last_frame.exists(),
            "shared_path_recorded": info.get("last_frame_shared_path") == str(shared_last_frame),
            "content_copied": shared_last_frame.read_bytes() == b"fake-last-frame",
        }

        for name, ok in checks.items():
            print(f"{name}={ok}")

        if all(checks.values()):
            print("SHARED_LAST_FRAME_COPY_OK")
            return 0

    print("SHARED_LAST_FRAME_COPY_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
