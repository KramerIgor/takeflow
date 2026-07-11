import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
SAFE_OUTPUT_ROOT = PROJECT_ROOT / "tmp_test_output"


def run_check(label: str, args: list[str]) -> bool:
    print(f"== {label} ==")
    env = os.environ.copy()
    env["PYTHON_DOTENV_DISABLED"] = "1"
    env.setdefault("SEGMIND_API_KEY", "")
    env.setdefault("OUTPUT_ROOT", str(SAFE_OUTPUT_ROOT))
    result = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(result.stdout, end="")
    print(f"{label}_status={result.returncode}")
    return result.returncode == 0


def text_contains(path: Path, needle: str) -> bool:
    return needle in path.read_text(encoding="utf-8")


def check_docs_and_start_script() -> bool:
    checks = {
        "readme_product_docs": text_contains(PROJECT_ROOT / "README.md", "User Guide")
        and text_contains(PROJECT_ROOT / "README.md", "Agent and Contributor Guide"),
        "project_state_stage11": text_contains(PROJECT_ROOT / "docs" / "PROJECT_STATE.md", "Stage 11"),
        "agents_stage11": text_contains(PROJECT_ROOT / "AGENTS.md", "Stage 11"),
        "start_script_exists": (PROJECT_ROOT / "scripts" / "start_gui.sh").exists(),
        "start_script_uses_uvicorn": text_contains(PROJECT_ROOT / "scripts" / "start_gui.sh", "uvicorn app.main:app"),
    }

    for name, ok in checks.items():
        print(f"{name}={ok}")

    return all(checks.values())


def main() -> int:
    print("=== Stage 11 final diagnostics ===")

    checks = [
        check_docs_and_start_script(),
        run_check(
            "compileall",
            [
                str(PYTHON),
                "-m",
                "compileall",
                "app/main.py",
                "scripts/check_stage11_final_diagnostics.py",
                "scripts/check_stage11_ui_polish.py",
                "scripts/check_stage9_batch_import_dry_run.py",
                "scripts/check_cost_estimates.py",
                "scripts/check_seedance_model_options.py",
                "scripts/check_queue_history_cards.py",
                "scripts/check_frontend_i18n_static.py",
                "scripts/check_frontend_modules.py",
                "scripts/check_prompt_reference_cost_ui.py",
                "scripts/check_output_root_selector.py",
                "scripts/check_release_readiness.py",
                "scripts/check_first_run_defaults.py",
                "scripts/check_gui_add_to_queue.py",
                "scripts/check_parallel_queue_scheduler.py",
                "scripts/check_queue_modes_route.py",
                "scripts/check_macos_release.py",
                "scripts/check_dragdrop_js_regression.py",
                "scripts/check_refresh_guard.py",
                "scripts/check_project_scoped_history_queue.py",
                "scripts/check_shared_last_frame_copy.py",
                "scripts/check_history_edit_refs.py",
                "scripts/check_run_storage_layout.py",
            ],
        ),
        run_check("stage11_ui_polish", [str(PYTHON), "-u", "scripts/check_stage11_ui_polish.py"]),
        run_check("stage9_batch_import", [str(PYTHON), "-u", "scripts/check_stage9_batch_import_dry_run.py"]),
        run_check("stage8_backend_chaining", [str(PYTHON), "-u", "scripts/check_stage8_backend_chaining_dry_run.py"]),
        run_check("stage8_tabs_ui", [str(PYTHON), "-u", "scripts/check_stage8_tabs_ui.py"]),
        run_check("cost_estimates", [str(PYTHON), "-u", "scripts/check_cost_estimates.py"]),
        run_check("seedance_model_options", [str(PYTHON), "-u", "scripts/check_seedance_model_options.py"]),
        run_check("queue_history_cards", [str(PYTHON), "-u", "scripts/check_queue_history_cards.py"]),
        run_check("frontend_i18n_static", [str(PYTHON), "-u", "scripts/check_frontend_i18n_static.py"]),
        run_check("frontend_modules", [str(PYTHON), "-u", "scripts/check_frontend_modules.py"]),
        run_check("prompt_reference_cost_ui", [str(PYTHON), "-u", "scripts/check_prompt_reference_cost_ui.py"]),
        run_check("output_root_selector", [str(PYTHON), "-u", "scripts/check_output_root_selector.py"]),
        run_check("release_readiness", [str(PYTHON), "-u", "scripts/check_release_readiness.py"]),
        run_check("first_run_defaults", [str(PYTHON), "-u", "scripts/check_first_run_defaults.py"]),
        run_check("gui_add_to_queue", [str(PYTHON), "-u", "scripts/check_gui_add_to_queue.py"]),
        run_check("parallel_queue_scheduler", [str(PYTHON), "-u", "scripts/check_parallel_queue_scheduler.py"]),
        run_check("queue_modes_route", [str(PYTHON), "-u", "scripts/check_queue_modes_route.py"]),
        run_check("macos_release", [str(PYTHON), "-u", "scripts/check_macos_release.py"]),
        run_check("dragdrop_js_regression", [str(PYTHON), "-u", "scripts/check_dragdrop_js_regression.py"]),
        run_check("refresh_guard", [str(PYTHON), "-u", "scripts/check_refresh_guard.py"]),
        run_check("project_scoped_history_queue", [str(PYTHON), "-u", "scripts/check_project_scoped_history_queue.py"]),
        run_check("shared_last_frame_copy", [str(PYTHON), "-u", "scripts/check_shared_last_frame_copy.py"]),
        run_check("history_edit_refs", [str(PYTHON), "-u", "scripts/check_history_edit_refs.py"]),
        run_check("run_storage_layout", [str(PYTHON), "-u", "scripts/check_run_storage_layout.py"]),
    ]

    if all(checks):
        print("RESULT=STAGE11_FINAL_DIAGNOSTICS_OK")
        return 0

    print("RESULT=STAGE11_FINAL_DIAGNOSTICS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
