from pathlib import Path
import os
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.pop("OUTPUT_DIR", None)
os.environ.pop("OUTPUT_ROOT", None)

from app.runtime_paths import default_output_dir


def main() -> int:
    output_dir = default_output_dir()
    normalized = str(output_dir).replace("\\", "/").lower()
    checks = {
        "default_project_is_my_first_project": output_dir.name == "MyFirstProject",
        "default_root_is_outputs": output_dir.parent.name == "outputs",
        "default_has_no_wsl_mount": "/mnt/" not in normalized,
        "default_has_no_personal_project": ("psai" + "lor") not in normalized,
    }
    for name, value in checks.items():
        print(f"{name}={value}")
    print(f"default_output_dir={output_dir}")
    ok = all(checks.values())
    print("RESULT=FIRST_RUN_DEFAULTS_OK" if ok else "RESULT=FIRST_RUN_DEFAULTS_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
