from pathlib import Path
import shutil
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.storage import next_take_number, to_windows_path


def main() -> int:
    print("=== Storage helper check ===")

    tmp = Path(tempfile.mkdtemp(prefix="seedance_storage_test_"))

    try:
        base = tmp / "results" / "_inbox"
        base.mkdir(parents=True)

        (base / "take_000001").mkdir()
        (base / "take_000002").mkdir()
        (base / "not_a_take").mkdir()

        next_number = next_take_number(base)

        print("tmp_base=", base, sep="")
        print("next_take_number=", next_number, sep="")
        print("windows_path_c=", to_windows_path("/mnt/c/AI_OUTPUT/Psailor_kun/results/_inbox/take_000001"), sep="")
        print("windows_path_d=", to_windows_path("/mnt/d/AI_OUTPUT/test"), sep="")

        if (
            next_number == 3
            and to_windows_path("/mnt/c/AI_OUTPUT/Psailor_kun/results/_inbox/take_000001").startswith("C:\\")
            and to_windows_path("/mnt/d/AI_OUTPUT/test").startswith("D:\\")
        ):
            print("RESULT=STORAGE_HELPER_OK")
            return 0

        print("RESULT=STORAGE_HELPER_FAILED")
        return 1

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
