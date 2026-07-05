from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

import app.main as main
from app.db import create_task, delete_task
from app.projects import get_active_project_dir, get_active_project_name, get_output_root


def expect(name: str, condition: bool) -> bool:
    print(f"{name}={condition}")
    return bool(condition)


def history_json_items(html: str) -> list[dict]:
    matches = re.findall(
        r'<script type="application/json" class="history-item-data">\s*(.*?)\s*</script>',
        html,
        flags=re.DOTALL,
    )
    items = []
    for raw in matches:
        try:
            items.append(json.loads(raw))
        except json.JSONDecodeError:
            pass
    return items


def make_params(prompt: str, mode: str) -> dict:
    return {
        "project_name": get_active_project_name(),
        "project_dir": str(get_active_project_dir()),
        "episode_name": "Episode_01",
        "scene_name": "Scene_001",
        "single_generation_name": "History_Edit_Refs_Check",
        "name": "History_Edit_Refs_Check",
        "model": "seedance-2.0-fast",
        "prompt": prompt,
        "reference_images": [],
        "reference_videos": [],
        "reference_audios": [],
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "generate_audio": False,
        "seed": -1,
        "return_last_frame": True,
        "skip_moderation": False,
        "mode": mode,
    }


def main_check() -> int:
    print("=== History edit refs check ===")

    marker = uuid.uuid4().hex[:8]
    prompt = f"HISTORY_EDIT_REFS_CHECK_{marker}"
    created_tasks = []

    with TemporaryDirectory() as tmp:
        external_ref = Path(tmp) / f"external_ref_{marker}.png"
        external_ref.write_bytes(b"not-a-real-png-but-valid-reference-path")

        output_root = get_output_root().resolve()
        ref_outside_output_root = not external_ref.resolve().is_relative_to(output_root)

        refs = [
            {
                "role": "image 1",
                "original_filename": external_ref.name,
                "local_path": str(external_ref),
                "source": "test_external_reference",
                "media_type": "image",
                "size_bytes": external_ref.stat().st_size,
            }
        ]

        history_task_id = create_task(
            model="seedance-2.0-fast",
            prompt=prompt,
            params=make_params(prompt, "single_generation_paid"),
            refs=refs,
            status="completed",
        )
        queue_task_id = create_task(
            model="seedance-2.0-fast",
            prompt=f"{prompt}_QUEUE",
            params=make_params(f"{prompt}_QUEUE", "queued_no_generation_yet"),
            refs=refs,
            status="queued",
        )
        created_tasks.extend([history_task_id, queue_task_id])

        try:
            client = TestClient(main.app)
            html = client.get("/").text
            json_items = history_json_items(html)
            matching_items = [
                item for item in json_items if item.get("prompt") in {prompt, f"{prompt}_QUEUE"}
            ]
            matching_refs = [
                ref
                for item in matching_items
                for ref in (item.get("refs") or [])
                if ref.get("filename") == external_ref.name
            ]

            backend_refs = main.safe_existing_reference_refs([str(external_ref)])

            checks = [
                expect("external_ref_outside_output_root", ref_outside_output_root),
                expect("history_and_queue_items_rendered", len(matching_items) == 2),
                expect("refs_present_in_history_json", len(matching_refs) == 2),
                expect("refs_marked_existing", all(ref.get("exists") is True for ref in matching_refs)),
                expect("refs_keep_local_path", all(ref.get("local_path") == str(external_ref.resolve()) for ref in matching_refs)),
                expect("external_preview_not_exposed", all(not ref.get("preview_url") for ref in matching_refs)),
                expect("backend_accepts_existing_external_ref", len(backend_refs) == 1 and backend_refs[0].get("local_path") == str(external_ref.resolve())),
            ]
        finally:
            for task_id in created_tasks:
                delete_task(task_id)

    print("test_tasks_deleted=True")
    print("new_paid_submit_started=False")

    if all(checks):
        print("RESULT=HISTORY_EDIT_REFS_OK")
        return 0

    print("RESULT=HISTORY_EDIT_REFS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_check())
