from pathlib import Path
import json
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app.queue_worker as worker


def main() -> int:
    print("=== Worker API last-frame save check ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        run_dir = Path(temp_dir) / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        fake_image_source = Path(temp_dir) / "fake_last_frame_source.png"
        fake_image_source.write_bytes(b"fake_png_bytes_for_no_paid_test")

        fake_url = "https://example.com/fake_last_frame.png"

        original_download_file = worker._download_file

        def fake_download_file(url: str, path: Path) -> None:
            if url != fake_url:
                raise RuntimeError(f"unexpected_url={url}")

            path.write_bytes(fake_image_source.read_bytes())

        worker._download_file = fake_download_file

        try:
            result_data = {
                "output": "https://example.com/output.mp4",
                "video": {
                    "url": "https://example.com/output.mp4",
                    "content_type": "video/mp4",
                },
                "last_frame": {
                    "url": fake_url,
                    "content_type": "image/png",
                    "file_name": "last_frame.png",
                },
            }

            info = worker._save_api_last_frame_if_present(result_data, run_dir)

            no_frame_info = worker._save_api_last_frame_if_present(
                {
                    "output": "https://example.com/output.mp4",
                    "video": {
                        "url": "https://example.com/output.mp4",
                        "content_type": "video/mp4",
                    },
                },
                run_dir,
            )

        finally:
            worker._download_file = original_download_file

        last_frame_path = run_dir / "last_frame.png"

        print("last_frame_found=", info.get("last_frame_found"), sep="")
        print("last_frame_source=", info.get("last_frame_source"), sep="")
        print("last_frame_path=", info.get("last_frame_path"), sep="")
        print("last_frame_key_path=", info.get("last_frame_key_path"), sep="")
        print("last_frame_candidate_score_positive=", (info.get("last_frame_candidate_score") or 0) > 0, sep="")
        print("last_frame_file_exists=", last_frame_path.exists(), sep="")
        print("last_frame_file_size=", last_frame_path.stat().st_size if last_frame_path.exists() else 0, sep="")
        print("video_only_last_frame_found=", no_frame_info.get("last_frame_found"), sep="")
        print("new_paid_submit_started=False")

        ok = (
            info.get("last_frame_found") is True
            and info.get("last_frame_source") == "api"
            and info.get("last_frame_path") == str(last_frame_path)
            and info.get("last_frame_key_path") == "last_frame.url"
            and (info.get("last_frame_candidate_score") or 0) > 0
            and last_frame_path.exists()
            and last_frame_path.stat().st_size > 0
            and no_frame_info.get("last_frame_found") is False
        )

        if ok:
            print("RESULT=WORKER_API_LAST_FRAME_SAVE_OK")
            return 0

        print("RESULT=WORKER_API_LAST_FRAME_SAVE_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
