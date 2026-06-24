from pathlib import Path
import asyncio
import os
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import app.main as main


def assert_ok(name, condition):
    print(f"{name}=", bool(condition), sep="")
    return bool(condition)


def check_parser():
    prompts = main.parse_chain_prompts(
        """
        First prompt
        ---
        Second prompt

        ---
        Third prompt
        """
    )

    rejects_short = False
    try:
        main.parse_chain_prompts("Only one prompt")
    except ValueError:
        rejects_short = True

    many_prompts = "\n---\n".join(f"Prompt {index}" for index in range(1, 25))
    capped_prompts = main.parse_chain_prompts(many_prompts)

    return [
        assert_ok("parser_creates_3_prompt_items", prompts == ["First prompt", "Second prompt", "Third prompt"]),
        assert_ok("parser_rejects_fewer_than_2_items", rejects_short),
        assert_ok("parser_caps_over_20_items", len(capped_prompts) == 20 and capped_prompts[-1] == "Prompt 20"),
    ]


async def check_route_creates_chain_without_db_pollution():
    created_calls = []
    next_task_id = {"value": 700}

    with tempfile.TemporaryDirectory(prefix="stage8_chain_builder_") as temp_dir:
        temp_project_dir = Path(temp_dir) / "Project"
        temp_project_dir.mkdir(parents=True)

        def fake_create_task(**kwargs):
            task_id = next_task_id["value"]
            next_task_id["value"] += 1
            created_calls.append({"task_id": task_id, **kwargs})
            return task_id

        def fake_base_context(request, **kwargs):
            return kwargs

        def fake_template_response(template_name, context, status_code=200):
            return {
                "template_name": template_name,
                "context": context,
                "status_code": status_code,
            }

        async def fake_save_uploaded_refs(reference_images, refs_dir):
            return [
                {
                    "role": "image 1",
                    "original_filename": "shared.png",
                    "local_path": str(Path(refs_dir) / "reference_01.png"),
                    "size_bytes": 10,
                }
            ]

        originals = {
            "create_task": main.create_task,
            "base_context": main.base_context,
            "save_uploaded_refs": main.save_uploaded_refs,
            "template_response": main.templates.TemplateResponse,
            "get_active_project_name": main.projects_module.get_active_project_name,
            "get_active_project_dir": main.projects_module.get_active_project_dir,
        }

        main.create_task = fake_create_task
        main.base_context = fake_base_context
        main.save_uploaded_refs = fake_save_uploaded_refs
        main.templates.TemplateResponse = fake_template_response
        main.projects_module.get_active_project_name = lambda: "Test_project"
        main.projects_module.get_active_project_dir = lambda: temp_project_dir

        try:
            response = await main.add_continuation_chain(
                request=None,
                chain_prompts="First\n---\nSecond\n---\nThird",
                model="seedance-2.0-fast",
                duration=4,
                resolution="480p",
                aspect_ratio="16:9",
                chain_episode_name="Episode_01",
                chain_scene_name="Scene_001",
                seed=-1,
                generate_audio=None,
                reference_images=[],
            )
        finally:
            main.create_task = originals["create_task"]
            main.base_context = originals["base_context"]
            main.save_uploaded_refs = originals["save_uploaded_refs"]
            main.templates.TemplateResponse = originals["template_response"]
            main.projects_module.get_active_project_name = originals["get_active_project_name"]
            main.projects_module.get_active_project_dir = originals["get_active_project_dir"]

    params = [call["params"] for call in created_calls]
    refs = [call["refs"] for call in created_calls]
    chain_ids = {item.get("continuation_chain_id") for item in params}
    first = params[0] if params else {}
    children = params[1:]
    all_payload_text = repr(params)

    return [
        assert_ok("route_response_ok", response["status_code"] == 200),
        assert_ok("route_created_3_queued_task_calls", len(created_calls) == 3 and all(call["status"] == "queued" for call in created_calls)),
        assert_ok("first_task_has_no_continuation_mode", "continuation_mode" not in first),
        assert_ok("first_task_has_no_parent_task_id", "parent_task_id" not in first),
        assert_ok("first_task_has_shared_refs_only", len(refs[0]) == 1 and refs[1] == [] and refs[2] == []),
        assert_ok(
            "child_tasks_have_last_frame_reference_mode",
            all(item.get("continuation_mode") == "last_frame_as_reference" for item in children),
        ),
        assert_ok(
            "child_parent_task_id_points_to_previous_created_task",
            children[0].get("parent_task_id") == created_calls[0]["task_id"]
            and children[1].get("parent_task_id") == created_calls[1]["task_id"],
        ),
        assert_ok("all_tasks_return_last_frame_true", all(item.get("return_last_frame") is True for item in params)),
        assert_ok("all_tasks_share_one_chain_id", len(chain_ids) == 1 and None not in chain_ids),
        assert_ok("continuation_index_increments", [item.get("continuation_index") for item in params] == [1, 2, 3]),
        assert_ok(
            "same_episode_and_scene_for_all_tasks",
            all(item.get("episode_name") == "Episode_01" and item.get("scene_name") == "Scene_001" for item in params),
        ),
        assert_ok("first_frame_url_absent_everywhere", "first_frame_url" not in all_payload_text),
        assert_ok("new_paid_submit_started_false", "No paid generation was started." in response["context"].get("message", "")),
    ]


def main_run():
    print("=== Stage 8 Chain Builder dry-run check ===")

    results = []
    results.extend(check_parser())
    results.extend(asyncio.run(check_route_creates_chain_without_db_pollution()))

    if all(results):
        print("RESULT=STAGE8_CHAIN_BUILDER_DRY_RUN_OK")
        return 0

    print("RESULT=STAGE8_CHAIN_BUILDER_DRY_RUN_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
