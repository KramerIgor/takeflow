import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"


def run_check(label: str, args: list[str]) -> bool:
    print(f"== {label} ==")
    env = os.environ.copy()
    env["PYTHON_DOTENV_DISABLED"] = "1"
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
        "readme_stage11": text_contains(PROJECT_ROOT / "README.md", "Stage 11"),
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
                "scripts/check_stage10_night_mode_dry_run.py",
                "scripts/check_stage9_batch_import_dry_run.py",
            ],
        ),
        run_check("stage10_night_mode", [str(PYTHON), "-u", "scripts/check_stage10_night_mode_dry_run.py"]),
        run_check("stage9_batch_import", [str(PYTHON), "-u", "scripts/check_stage9_batch_import_dry_run.py"]),
        run_check("stage8_backend_chaining", [str(PYTHON), "-u", "scripts/check_stage8_backend_chaining_dry_run.py"]),
        run_check("stage8_tabs_ui", [str(PYTHON), "-u", "scripts/check_stage8_tabs_ui.py"]),
    ]

    if all(checks):
        print("RESULT=STAGE11_FINAL_DIAGNOSTICS_OK")
        return 0

    print("RESULT=STAGE11_FINAL_DIAGNOSTICS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
