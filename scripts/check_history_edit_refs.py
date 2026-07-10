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
from app.db import create_task, delete_task, update_task_fields
from app.projects import get_active_project_dir, get_active_project_name, get_output_root
from scripts.frontend_static_utils import read_static_js


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


def to_mnt_c_path(path: Path) -> str | None:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if drive != "c":
        return None
    rest = str(resolved)[3:].replace("\\", "/")
    return f"/mnt/c/{rest}"


def main_check() -> int:
    print("=== History edit refs check ===")

    marker = uuid.uuid4().hex[:8]
    prompt = f"HISTORY_EDIT_REFS_CHECK_{marker}"
    created_tasks = []

    output_root = get_output_root().resolve()
    output_test_dir = get_active_project_dir() / f"_history_edit_refs_check_{marker}"

    with TemporaryDirectory() as tmp:
        external_ref = Path(tmp) / f"external_ref_{marker}.png"
        external_ref.write_bytes(b"not-a-real-png-but-valid-reference-path")

        ref_outside_output_root = not external_ref.resolve().is_relative_to(output_root)
        output_test_dir.mkdir(parents=True, exist_ok=True)
        wsl_ref = output_test_dir / f"wsl_ref_{marker}.png"
        wsl_ref.write_bytes(b"fake-wsl-ref")
        wsl_video = output_test_dir / f"wsl_video_{marker}.mp4"
        wsl_video.write_bytes(b"fake-mp4")
        wsl_ref_path = to_mnt_c_path(wsl_ref) or str(wsl_ref)
        wsl_video_path = to_mnt_c_path(wsl_video) or str(wsl_video)

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
        wsl_task_id = create_task(
            model="seedance-2.0-fast",
            prompt=f"{prompt}_WSL_PATHS",
            params=make_params(f"{prompt}_WSL_PATHS", "single_generation_paid"),
            refs=[
                {
                    "role": "image 1",
                    "original_filename": wsl_ref.name,
                    "local_path": wsl_ref_path,
                    "source": "test_wsl_reference_path",
                    "media_type": "image",
                    "size_bytes": wsl_ref.stat().st_size,
                }
            ],
            status="completed",
        )
        update_task_fields(wsl_task_id, output_path=wsl_video_path, run_dir=str(output_test_dir))
        created_tasks.extend([history_task_id, queue_task_id, wsl_task_id])

        try:
            client = TestClient(main.app)
            html = client.get("/").text
            view_items = main.single_generation_history_for_view(limit=80)
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
            wsl_items = [
                item for item in json_items if item.get("prompt") == f"{prompt}_WSL_PATHS"
            ]
            wsl_view_items = [
                item for item in view_items if item.get("prompt") == f"{prompt}_WSL_PATHS"
            ]
            wsl_refs = [
                ref
                for item in wsl_items
                for ref in (item.get("refs") or [])
                if ref.get("filename") == wsl_ref.name
            ]

            backend_refs = main.safe_existing_reference_refs([str(external_ref)])
            backend_wsl_refs = main.safe_existing_reference_refs([wsl_ref_path])
            renamed_ref = output_test_dir / "reference_01_taxedo_brew.png"
            renamed_ref.write_bytes(b"fake")
            preserved_name_refs = main.safe_existing_reference_refs(
                [str(renamed_ref)],
                [
                    json.dumps(
                        {
                            "local_path": str(renamed_ref),
                            "original_filename": "taxedo brew.png",
                            "filename": "taxedo brew.png",
                            "media_type": "image",
                        }
                    )
                ],
            )
            template_text = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
            app_js_text = read_static_js(PROJECT_ROOT)
            client_text = template_text + "\n" + app_js_text

            checks = [
                expect("external_ref_outside_output_root", ref_outside_output_root),
                expect("history_and_queue_items_rendered", len(matching_items) == 2),
                expect("refs_present_in_history_json", len(matching_refs) == 2),
                expect("refs_marked_existing", all(ref.get("exists") is True for ref in matching_refs)),
                expect("refs_keep_local_path", all(ref.get("local_path") == str(external_ref.resolve()) for ref in matching_refs)),
                expect("external_preview_not_exposed", all(not ref.get("preview_url") for ref in matching_refs)),
                expect("backend_accepts_existing_external_ref", len(backend_refs) == 1 and backend_refs[0].get("local_path") == str(external_ref.resolve())),
                expect("wsl_path_item_rendered", len(wsl_items) == 1),
                expect("wsl_ref_marked_existing", len(wsl_refs) == 1 and wsl_refs[0].get("exists") is True),
                expect("wsl_ref_normalized_to_windows_path", len(wsl_refs) == 1 and wsl_refs[0].get("local_path") == str(wsl_ref.resolve())),
                expect("wsl_ref_preview_exposed_inside_output_root", len(wsl_refs) == 1 and bool(wsl_refs[0].get("preview_url"))),
                expect("wsl_video_preview_url_present", bool(wsl_view_items[0].get("output_preview_url")) if wsl_view_items else False),
                expect("backend_accepts_existing_wsl_ref", len(backend_wsl_refs) == 1 and backend_wsl_refs[0].get("local_path") == str(wsl_ref.resolve())),
                expect("backend_preserves_existing_ref_original_name", len(preserved_name_refs) == 1 and preserved_name_refs[0].get("original_filename") == "taxedo brew.png"),
                expect("frontend_sends_existing_ref_metadata", "existing_reference_metadata" in client_text),
            ]
        finally:
            for task_id in created_tasks:
                delete_task(task_id)
            import shutil

            shutil.rmtree(output_test_dir, ignore_errors=True)

    print("test_tasks_deleted=True")
    print("new_paid_submit_started=False")

    if all(checks):
        print("RESULT=HISTORY_EDIT_REFS_OK")
        return 0

    print("RESULT=HISTORY_EDIT_REFS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_check())
