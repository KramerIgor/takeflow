from pathlib import Path
import os
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import app.queue_worker as worker


class FakeResponse:
    def __init__(self, data, ok=True, status_code=200):
        self.data = data
        self.ok = ok
        self.status_code = status_code
        self.text_preview = ""


class FakeSegmindClient:
    record = None

    def __init__(self, model=None, timeout=180.0):
        self.model = model
        self.timeout = timeout
        FakeSegmindClient.record["client_constructed"] = True

    def upload_asset(self, local_path):
        FakeSegmindClient.record["uploaded_paths"].append(str(local_path))
        return FakeResponse({"urls": [f"https://uploaded.example/{Path(local_path).name}"]})

    def extract_uploaded_asset_url(self, response):
        return response.data["urls"][0]

    def build_seedance_payload(self, **kwargs):
        FakeSegmindClient.record["payload"] = dict(kwargs)
        return dict(kwargs)

    def submit_seedance_async(self, payload):
        FakeSegmindClient.record["submitted_payload"] = dict(payload)
        return FakeResponse({"request_id": "fake-request-id"})

    def extract_request_id(self, response):
        return response.data["request_id"]

    def get_request_status(self, request_id):
        return FakeResponse({"status": "COMPLETED"})

    def extract_status(self, response):
        return response.data["status"]

    def get_request_result(self, request_id):
        return FakeResponse({"video": {"url": "https://example.test/output.mp4"}})


class ExplodingSegmindClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("SegmindClient should not be constructed for waiting parent.")


def base_child_task(parent_task_id, refs=None):
    return {
        "id": 200,
        "status": "queued",
        "model": "seedance-2.0-fast",
        "prompt": "child prompt",
        "params": {
            "project_name": "Test_project",
            "episode_name": "Episode_01",
            "scene_name": "Scene_001",
            "duration": 4,
            "resolution": "480p",
            "aspect_ratio": "16:9",
            "generate_audio": False,
            "seed": -1,
            "return_last_frame": True,
            "continuation_mode": "last_frame_as_reference",
            "parent_task_id": parent_task_id,
            "parent_take_stem": "Episode_01_Scene_001_take_000001",
        },
        "refs": refs or [],
        "request_id": None,
        "output_path": None,
        "run_dir": None,
        "error": None,
    }


def patch_worker(monkeypatches):
    originals = {}
    for name, value in monkeypatches.items():
        originals[name] = getattr(worker, name)
        setattr(worker, name, value)
    return originals


def restore_worker(originals):
    for name, value in originals.items():
        setattr(worker, name, value)


def same_file(path_a, path_b):
    try:
        return Path(path_a).samefile(path_b)
    except (OSError, ValueError):
        return os.path.normcase(str(Path(path_a).resolve())) == os.path.normcase(str(Path(path_b).resolve()))


def contains_file(paths, expected):
    return any(same_file(path, expected) for path in paths)


def run_waiting_parent_case():
    updates = []
    child = base_child_task(parent_task_id=100)
    parent = {"id": 100, "status": "queued", "params": {}, "refs": []}

    originals = patch_worker(
        {
            "get_next_queued_task": lambda: child,
            "get_task": lambda task_id: parent if task_id == 100 else None,
            "update_task_fields": lambda task_id, **fields: updates.append((task_id, fields)),
            "SegmindClient": ExplodingSegmindClient,
        }
    )

    try:
        result = worker.process_next_queued_task_real()
    finally:
        restore_worker(originals)

    return {
        "result": result,
        "updates": updates,
    }


def run_missing_last_frame_case():
    updates = []
    child = base_child_task(parent_task_id=101)
    parent = {
        "id": 101,
        "status": "completed",
        "params": {},
        "refs": [],
        "run_dir": "/tmp/nonexistent_stage8_parent_run",
        "output_path": None,
    }

    originals = patch_worker(
        {
            "get_next_queued_task": lambda: child,
            "get_task": lambda task_id: parent if task_id == 101 else None,
            "update_task_fields": lambda task_id, **fields: updates.append((task_id, fields)),
            "SegmindClient": ExplodingSegmindClient,
        }
    )

    try:
        result = worker.process_next_queued_task_real()
    finally:
        restore_worker(originals)

    return {
        "result": result,
        "updates": updates,
    }


def run_completed_parent_case(existing_manual_ref=False):
    updates = []

    with tempfile.TemporaryDirectory(prefix="stage8_backend_chain_") as temp_dir:
        root = Path(temp_dir)
        parent_run_dir = root / "runs" / "Episode_01_Scene_001_take_000001"
        parent_run_dir.mkdir(parents=True)
        parent_last_frame = parent_run_dir / "last_frame.png"
        parent_last_frame.write_bytes(b"fake-png")
        grandparent_run_dir = root / "runs" / "Episode_01_Scene_001_take_000000"
        grandparent_run_dir.mkdir(parents=True)
        grandparent_last_frame = grandparent_run_dir / "last_frame.png"
        grandparent_last_frame.write_bytes(b"older-fake-png")

        child_run_dir = root / "runs" / "Episode_01_Scene_001_take_000002"
        final_video_path = root / "videos" / "Episode_01_Scene_001_take_000002.mp4"

        refs = []
        if existing_manual_ref:
            refs.append(
                {
                    "role": "parent_last_frame_reference",
                    "local_path": str(parent_last_frame),
                    "source": "continue_from_previous_take",
                    "parent_task_id": 102,
                }
            )

        child = base_child_task(parent_task_id=102, refs=refs)
        parent = {
            "id": 102,
            "status": "completed",
            "params": {"parent_last_frame_path": str(grandparent_last_frame)},
            "refs": [],
            "run_dir": str(parent_run_dir),
            "output_path": str(root / "videos" / "Episode_01_Scene_001_take_000001.mp4"),
        }

        FakeSegmindClient.record = {
            "client_constructed": False,
            "uploaded_paths": [],
            "payload": None,
            "submitted_payload": None,
        }

        def fake_download(url, path):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b"fake-video")

        def fake_final_video_path(run_dir):
            final_video_path.parent.mkdir(parents=True, exist_ok=True)
            return final_video_path

        originals = patch_worker(
            {
                "get_next_queued_task": lambda: child,
                "get_task": lambda task_id: parent if task_id == 102 else None,
                "update_task_fields": lambda task_id, **fields: updates.append((task_id, fields)),
                "SegmindClient": FakeSegmindClient,
                "_allocate_run_dir_for_task": lambda params: child_run_dir,
                "_final_video_path_for_run_dir": fake_final_video_path,
                "_download_file": fake_download,
            }
        )

        try:
            result = worker.process_next_queued_task_real()
        finally:
            restore_worker(originals)

        return {
            "result": result,
            "updates": updates,
            "record": dict(FakeSegmindClient.record),
            "parent_last_frame": str(parent_last_frame),
            "grandparent_last_frame": str(grandparent_last_frame),
        }


def main_run():
    print("=== Stage 8 backend chaining dry-run check ===")

    waiting = run_waiting_parent_case()
    waiting_ok = (
        waiting["result"].get("processed") is False
        and waiting["result"].get("reason") == "waiting_for_parent_task"
        and waiting["result"].get("parent_status") == "queued"
        and not waiting["updates"]
    )
    print("waiting_parent_not_submitted=", waiting_ok, sep="")

    missing = run_missing_last_frame_case()
    missing_update = missing["updates"][0][1] if missing["updates"] else {}
    missing_ok = (
        missing["result"].get("reason") == "parent_last_frame_missing"
        and missing_update.get("status") == "failed"
        and "last_frame.png was not found" in (missing_update.get("error") or "")
    )
    print("missing_last_frame_failed_without_submit=", missing_ok, sep="")

    completed = run_completed_parent_case(existing_manual_ref=False)
    payload = completed["record"]["payload"] or {}
    completed_ok = (
        completed["result"].get("status") == "completed"
        and contains_file(completed["record"]["uploaded_paths"], completed["parent_last_frame"])
        and not contains_file(completed["record"]["uploaded_paths"], completed["grandparent_last_frame"])
        and "https://uploaded.example/last_frame.png" in payload.get("reference_images", [])
        and "first_frame_url" not in payload
    )
    print("completed_parent_uploads_last_frame_reference=", completed_ok, sep="")

    manual = run_completed_parent_case(existing_manual_ref=True)
    manual_payload = manual["record"]["payload"] or {}
    manual_ok = (
        manual["result"].get("status") == "completed"
        and sum(same_file(path, manual["parent_last_frame"]) for path in manual["record"]["uploaded_paths"]) == 1
        and not contains_file(manual["record"]["uploaded_paths"], manual["grandparent_last_frame"])
        and "https://uploaded.example/last_frame.png" in manual_payload.get("reference_images", [])
        and "first_frame_url" not in manual_payload
    )
    print("manual_continue_task_shape_compatible=", manual_ok, sep="")

    print("first_frame_url_absent=", "first_frame_url" not in payload and "first_frame_url" not in manual_payload, sep="")
    print("new_paid_submit_started=False")

    ok = waiting_ok and missing_ok and completed_ok and manual_ok

    if ok:
        print("RESULT=STAGE8_BACKEND_CHAINING_DRY_RUN_OK")
        return 0

    print("RESULT=STAGE8_BACKEND_CHAINING_DRY_RUN_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
