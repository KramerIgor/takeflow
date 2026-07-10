from pathlib import Path
import json
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import queue_worker as worker
from app.segmind_client import SegmindResponse


def expect(name, condition):
    print(f"{name}={condition}")
    return bool(condition)


class FakeSegmindClient:
    def __init__(self, *args, **kwargs):
        pass

    def build_seedance_payload(self, **kwargs):
        return dict(kwargs)

    def submit_seedance_async(self, payload):
        return SegmindResponse(200, True, "https://fake.local/submit", {"request_id": "fake-request"}, "ok")

    def extract_request_id(self, response):
        return response.data["request_id"]

    def get_request_status(self, request_id):
        return SegmindResponse(200, True, "https://fake.local/status", {"status": "COMPLETED"}, "ok")

    def extract_status(self, response):
        return response.data["status"]

    def get_request_result(self, request_id):
        return SegmindResponse(
            200,
            True,
            "https://fake.local/result",
            {
                "output": "https://fake.local/output.mp4",
                "last_frame": {"url": "https://fake.local/last_frame.png"},
            },
            "ok",
        )

    def upload_asset(self, local_path):
        raise AssertionError("No references should be uploaded in this check")


def patch_worker(monkeypatches):
    originals = {}
    for name, value in monkeypatches.items():
        originals[name] = getattr(worker, name)
        setattr(worker, name, value)
    return originals


def restore_worker(originals):
    for name, value in originals.items():
        setattr(worker, name, value)


def main() -> int:
    print("=== Run storage layout check ===")

    updates = []
    with tempfile.TemporaryDirectory(prefix="seedance_storage_layout_") as temp_dir:
        root = Path(temp_dir)
        run_dir = root / "runs" / "Prompt_1_Single_Generation_take_000001"
        video_path = root / "videos" / "Prompt_1_Single_Generation_take_000001.mp4"
        duplicate_run_dir = root / "runs" / "Prompt_1_Single_Generation_take_000002"

        params = {
            "project_name": "storage_layout_test",
            "project_dir": str(root),
            "episode_name": "Prompt_1",
            "scene_name": "Single_Generation",
            "run_dir": str(run_dir),
            "video_path": str(video_path),
            "model": "seedance-2.0-mini",
            "prompt": "storage layout check",
            "reference_images": [],
            "reference_videos": [],
            "reference_audios": [],
            "duration": 4,
            "resolution": "480p",
            "aspect_ratio": "16:9",
            "generate_audio": True,
            "seed": -1,
            "return_last_frame": True,
            "skip_moderation": False,
            "mode": "single_generation_paid",
        }

        task = {
            "id": 9001,
            "status": "queued",
            "model": "seedance-2.0-mini",
            "prompt": params["prompt"],
            "params": params,
            "refs": [],
        }

        def fake_download(url, path):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if url.endswith(".mp4"):
                path.write_bytes(b"fake-mp4")
            else:
                path.write_bytes(b"fake-png")

        originals = patch_worker(
            {
                "SegmindClient": FakeSegmindClient,
                "_download_file": fake_download,
                "update_task_fields": lambda task_id, **fields: updates.append((task_id, fields)),
            }
        )

        try:
            result = worker._process_queued_task_real(task)
        finally:
            restore_worker(originals)

        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        shared_last_frame = root / "last_frames" / f"{run_dir.name}_last_frame.png"

        checks = [
            expect("worker_completed", result.get("status") == "completed"),
            expect("uses_existing_run_dir", result.get("run_dir") == str(run_dir)),
            expect("no_duplicate_run_dir", not duplicate_run_dir.exists()),
            expect("video_saved_in_videos", video_path.exists() and video_path.stat().st_size > 0),
            expect("no_run_output_mp4", not (run_dir / "output.mp4").exists()),
            expect("last_frame_saved_in_shared_folder", shared_last_frame.exists() and shared_last_frame.stat().st_size > 0),
            expect("no_run_last_frame_png", not (run_dir / "last_frame.png").exists()),
            expect("summary_video_path_is_final", summary.get("video_path") == str(video_path)),
            expect("summary_technical_output_empty", summary.get("technical_output_path") is None),
            expect("summary_last_frame_points_shared", summary.get("last_frame_path") == str(shared_last_frame)),
        ]

    if all(checks):
        print("RESULT=RUN_STORAGE_LAYOUT_OK")
        return 0

    print("RESULT=RUN_STORAGE_LAYOUT_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
