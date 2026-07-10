from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import main
from scripts.frontend_static_utils import read_static_js


def expect(name, condition):
    print(f"{name}={condition}")
    return bool(condition)


def has_error(report, field):
    return any(item.get("field") == field for item in report.get("errors", []))


def is_valid(report):
    return bool(report.get("valid_rows")) and not report.get("errors")


def make_csv(row):
    header = "episode_name,scene_name,prompt,model,duration,resolution,aspect_ratio,seed,generate_audio,reference_paths"
    return "\n".join([header, row])


def make_reference_paths(count: int) -> str:
    refs_dir = PROJECT_ROOT / "tmp_test_output" / "model_option_refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(count):
        path = refs_dir / f"ref_{index:02d}.png"
        path.write_bytes(b"seedance-test-ref")
        paths.append(str(path))
    return ";".join(paths)


def main_check():
    print("=== Seedance model options check ===")

    index_text = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    app_js = read_static_js(PROJECT_ROOT)
    client_text = index_text + "\n" + app_js
    standard = main.model_config_for_id("seedance-2.0")
    mini = main.model_config_for_id("seedance-2.0-mini")
    fast = main.model_config_for_id("seedance-2.0-fast")

    standard_4k_csv = main.parse_and_validate_batch_csv(
        make_csv("Episode_01,Scene_001,Prompt,seedance-2.0,4,4k,16:9,-1,true,")
    )
    mini_720_csv = main.parse_and_validate_batch_csv(
        make_csv("Episode_01,Scene_001,Prompt,seedance-2.0-mini,10,720p,21:9,-1,true,")
    )
    mini_1080_csv = main.parse_and_validate_batch_csv(
        make_csv("Episode_01,Scene_001,Prompt,seedance-2.0-mini,10,1080p,21:9,-1,true,")
    )
    mini_7s_csv = main.parse_and_validate_batch_csv(
        make_csv("Episode_01,Scene_001,Prompt,seedance-2.0-mini,7,480p,16:9,-1,true,")
    )
    fast_4k_csv = main.parse_and_validate_batch_csv(
        make_csv("Episode_01,Scene_001,Prompt,seedance-2.0-fast,4,4k,16:9,-1,true,")
    )
    too_many_refs_csv = main.parse_and_validate_batch_csv(
        make_csv(f"Episode_01,Scene_001,Prompt,seedance-2.0-fast,4,480p,16:9,-1,true,{make_reference_paths(10)}")
    )

    checks = [
        expect("mini_model_registered", "seedance-2.0-mini" in main.MODEL_CONFIGS),
        expect("standard_has_4k", "4k" in standard["resolutions"]),
        expect("mini_no_4k", "4k" not in mini["resolutions"]),
        expect("fast_no_4k", "4k" not in fast["resolutions"]),
        expect("mini_durations_exact", mini["durations"] == [4, 5, 6, 8, 10, 12, 15]),
        expect("reference_limits_configured", standard["reference_file_limit"] == 9 and mini["reference_file_limit"] == 9 and fast["reference_file_limit"] == 9),
        expect("standard_4k_csv_valid", is_valid(standard_4k_csv)),
        expect("mini_720_csv_valid", is_valid(mini_720_csv)),
        expect("mini_1080_csv_invalid", not is_valid(mini_1080_csv) and has_error(mini_1080_csv, "resolution")),
        expect("mini_7s_csv_invalid", not is_valid(mini_7s_csv) and has_error(mini_7s_csv, "duration")),
        expect("fast_4k_csv_invalid", not is_valid(fast_4k_csv) and has_error(fast_4k_csv, "resolution")),
        expect("csv_reference_limit_invalid", not is_valid(too_many_refs_csv) and has_error(too_many_refs_csv, "reference_paths")),
        expect("template_has_capabilities", "seedanceModelCapabilities" in client_text and "modelCapabilities" in index_text),
        expect("capabilities_include_reference_limit", "reference_file_limit" in client_text),
        expect("template_syncs_history", "window.seedanceSyncModelOptions(form, {" in app_js),
    ]

    if all(checks):
        print("RESULT=SEEDANCE_MODEL_OPTIONS_OK")
        return 0

    print("RESULT=SEEDANCE_MODEL_OPTIONS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_check())
