from pathlib import Path
import asyncio
import os
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import app.main as main


class FakeUpload:
    def __init__(self, text):
        self.filename = "batch.csv"
        self._text = text

    async def read(self):
        return self._text.encode("utf-8")


def assert_ok(name, condition):
    print(f"{name}=", bool(condition), sep="")
    return bool(condition)


def make_csv(rows):
    header = "episode_name,scene_name,prompt,model,duration,resolution,aspect_ratio,seed,generate_audio,reference_paths"
    return "\n".join([header, *rows])


def has_error(result, field):
    return any(error.get("field") == field for error in result.get("errors", []))


def check_parser_and_validation():
    with tempfile.TemporaryDirectory(prefix="stage9_refs_") as temp_dir:
        ref_a = Path(temp_dir) / "a.png"
        ref_b = Path(temp_dir) / "b.jpg"
        ref_a.write_bytes(b"a")
        ref_b.write_bytes(b"b")

        valid_csv = make_csv(
            [
                f"Episode_01,Scene_001,Prompt A,seedance-2.0-fast,4,480p,16:9,-1,false,{ref_a};{ref_b}",
                "Episode_01,Scene_002,Prompt B,seedance-2.0,5,720p,9:16,123,yes,",
            ]
        )
        valid = main.parse_and_validate_batch_csv(valid_csv)
        valid_with_bom = main.parse_and_validate_batch_csv("\ufeff" + valid_csv)

        chain_header = "episode_name,scene_name,prompt,model,duration,resolution,aspect_ratio,seed,generate_audio,reference_paths,continuation_group,continuation_index"
        chain_csv = "\n".join(
            [
                chain_header,
                f"Episode_01,Shot_001,Prompt A,seedance-2.0-fast,8,480p,16:9,-1,true,{ref_a},chain_a,1",
                f"Episode_01,Shot_002,Prompt B,seedance-2.0-fast,13,480p,16:9,-1,true,{ref_b},chain_a,2",
            ]
        )
        valid_chain = main.parse_and_validate_batch_csv(chain_csv)
        invalid_chain_index = main.parse_and_validate_batch_csv(
            "\n".join(
                [
                    chain_header,
                    f"Episode_01,Shot_001,Prompt A,seedance-2.0-fast,8,480p,16:9,-1,true,{ref_a},chain_a,nope",
                ]
            )
        )

        missing_header = main.parse_and_validate_batch_csv("prompt,model\nPrompt A,seedance-2.0-fast")
        empty_prompt = main.parse_and_validate_batch_csv(make_csv(["Episode_01,Scene_001, ,seedance-2.0-fast,4,480p,16:9,-1,false,"]))
        invalid_model = main.parse_and_validate_batch_csv(make_csv(["Episode_01,Scene_001,Prompt,bad-model,4,480p,16:9,-1,false,"]))
        invalid_duration = main.parse_and_validate_batch_csv(make_csv(["Episode_01,Scene_001,Prompt,seedance-2.0-fast,99,480p,16:9,-1,false,"]))
        invalid_resolution = main.parse_and_validate_batch_csv(make_csv(["Episode_01,Scene_001,Prompt,seedance-2.0-fast,4,999p,16:9,-1,false,"]))
        invalid_aspect = main.parse_and_validate_batch_csv(make_csv(["Episode_01,Scene_001,Prompt,seedance-2.0-fast,4,480p,2:7,-1,false,"]))
        invalid_seed = main.parse_and_validate_batch_csv(make_csv(["Episode_01,Scene_001,Prompt,seedance-2.0-fast,4,480p,16:9,nope,false,"]))
        invalid_audio = main.parse_and_validate_batch_csv(make_csv(["Episode_01,Scene_001,Prompt,seedance-2.0-fast,4,480p,16:9,-1,maybe,"]))
        missing_ref = main.parse_and_validate_batch_csv(make_csv(["Episode_01,Scene_001,Prompt,seedance-2.0-fast,4,480p,16:9,-1,false,/missing/ref.png"]))

        valid_refs = valid["valid_rows"][0]["reference_paths"] if valid["valid_rows"] else []

        return [
            assert_ok("valid_csv_with_2_rows_parses_successfully", len(valid["valid_rows"]) == 2 and not valid["errors"]),
            assert_ok("valid_csv_with_utf8_bom_parses_successfully", len(valid_with_bom["valid_rows"]) == 2 and not valid_with_bom["errors"]),
            assert_ok("missing_required_headers_returns_error", has_error(missing_header, "header")),
            assert_ok("empty_prompt_returns_row_error", has_error(empty_prompt, "prompt")),
            assert_ok("invalid_model_returns_row_error", has_error(invalid_model, "model")),
            assert_ok("invalid_duration_returns_row_error", has_error(invalid_duration, "duration")),
            assert_ok("invalid_resolution_returns_row_error", has_error(invalid_resolution, "resolution")),
            assert_ok("invalid_aspect_ratio_returns_row_error", has_error(invalid_aspect, "aspect_ratio")),
            assert_ok("invalid_seed_returns_row_error", has_error(invalid_seed, "seed")),
            assert_ok("invalid_generate_audio_returns_row_error", has_error(invalid_audio, "generate_audio")),
            assert_ok("missing_reference_path_returns_row_error", has_error(missing_ref, "reference_paths")),
            assert_ok("valid_reference_paths_split_by_semicolon", valid_refs == [str(ref_a), str(ref_b)]),
            assert_ok("valid_continuation_csv_parses", len(valid_chain["valid_rows"]) == 2 and not valid_chain["errors"]),
            assert_ok("continuation_duration_13_is_allowed", valid_chain["valid_rows"][1]["duration"] == 13),
            assert_ok("invalid_continuation_index_returns_error", has_error(invalid_chain_index, "continuation_index")),
        ]


async def check_route_modes_without_db_pollution():
    created_calls = []
    next_id = {"value": 900}

    with tempfile.TemporaryDirectory(prefix="stage9_route_") as temp_dir:
        temp_project_dir = Path(temp_dir) / "Project"
        temp_project_dir.mkdir(parents=True)
        ref = Path(temp_dir) / "ref.png"
        ref.write_bytes(b"ref")

        csv_text = make_csv(
            [
                f"Episode_01,Scene_001,Prompt A,seedance-2.0-fast,4,480p,16:9,-1,false,{ref}",
                "Episode_01,Scene_002,Prompt B,seedance-2.0,5,720p,9:16,42,true,",
            ]
        )
        chain_csv_text = "\n".join(
            [
                "episode_name,scene_name,prompt,model,duration,resolution,aspect_ratio,seed,generate_audio,reference_paths,continuation_group,continuation_index",
                f"Episode_Chain,Shot_001,Prompt A,seedance-2.0-fast,8,480p,21:9,-1,true,{ref},chain_a,1",
                f"Episode_Chain,Shot_002,Prompt B,seedance-2.0-fast,13,480p,21:9,-1,true,{ref},chain_a,2",
            ]
        )

        def fake_create_task(**kwargs):
            task_id = next_id["value"]
            next_id["value"] += 1
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

        originals = {
            "create_task": main.create_task,
            "base_context": main.base_context,
            "template_response": main.templates.TemplateResponse,
            "get_active_project_name": main.projects_module.get_active_project_name,
            "get_active_project_dir": main.projects_module.get_active_project_dir,
        }

        main.create_task = fake_create_task
        main.base_context = fake_base_context
        main.templates.TemplateResponse = fake_template_response
        main.projects_module.get_active_project_name = lambda: "Test_project"
        main.projects_module.get_active_project_dir = lambda: temp_project_dir

        try:
            preview_response = await main.batch_import(
                request=None,
                import_mode="preview",
                csv_file=FakeUpload(csv_text),
            )
            preview_call_count = len(created_calls)

            confirm_response = await main.batch_import(
                request=None,
                import_mode="confirm",
                csv_file=FakeUpload(csv_text),
            )
            chain_response = await main.batch_import(
                request=None,
                import_mode="confirm",
                csv_file=FakeUpload(chain_csv_text),
            )
        finally:
            main.create_task = originals["create_task"]
            main.base_context = originals["base_context"]
            main.templates.TemplateResponse = originals["template_response"]
            main.projects_module.get_active_project_name = originals["get_active_project_name"]
            main.projects_module.get_active_project_dir = originals["get_active_project_dir"]

    params = [call["params"] for call in created_calls]
    all_payload_text = repr(params)
    chain_params = params[2:]

    return [
        assert_ok("preview_mode_creates_no_tasks", preview_call_count == 0),
        assert_ok("confirm_mode_creates_expected_queued_task_calls", len(created_calls) == 4 and all(call["status"] == "queued" for call in created_calls)),
        assert_ok("created_task_params_return_last_frame_true", all(item.get("return_last_frame") is True for item in params)),
        assert_ok("created_task_params_include_batch_import_id", all(item.get("batch_import_id") for item in params)),
        assert_ok("created_task_params_include_batch_row_number", [item.get("batch_row_number") for item in params] == [2, 3, 2, 3]),
        assert_ok("continuation_csv_first_task_has_no_parent", chain_params[0].get("continuation_chain_id") and not chain_params[0].get("parent_task_id")),
        assert_ok("continuation_csv_second_task_uses_previous_parent", chain_params[1].get("continuation_mode") == "last_frame_as_reference" and chain_params[1].get("parent_task_id") == 902),
        assert_ok("continuation_csv_report_counts_links", chain_response["context"]["batch_import_report"]["continuation_link_count"] == 1),
        assert_ok("first_frame_url_absent_everywhere", "first_frame_url" not in all_payload_text),
        assert_ok("new_paid_submit_started_false", preview_response["context"]["batch_import_report"]["new_paid_submit_started"] is False and confirm_response["context"]["batch_import_report"]["new_paid_submit_started"] is False and chain_response["context"]["batch_import_report"]["new_paid_submit_started"] is False),
    ]


def main_run():
    print("=== Stage 9 Batch CSV Import dry-run check ===")

    results = []
    results.extend(check_parser_and_validation())
    results.extend(asyncio.run(check_route_modes_without_db_pollution()))

    if all(results):
        print("RESULT=STAGE9_BATCH_IMPORT_DRY_RUN_OK")
        return 0

    print("RESULT=STAGE9_BATCH_IMPORT_DRY_RUN_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
