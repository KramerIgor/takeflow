from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.costing import estimate_seedance_cost_info, cost_label


def expect(name, condition):
    print(f"{name}={condition}")
    return bool(condition)


def main():
    print("=== Cost estimate check ===")
    fast = estimate_seedance_cost_info(
        model="seedance-2.0-fast",
        duration=4,
        resolution="480p",
        aspect_ratio="16:9",
    )
    standard = estimate_seedance_cost_info(
        model="seedance-2.0",
        duration=5,
        resolution="720p",
        aspect_ratio="16:9",
    )
    ok = [
        expect("fast_cost_present", fast is not None),
        expect("fast_cost_value", fast and fast["amount_usd"] == 0.2248),
        expect("fast_cost_label", cost_label(fast) == "~$0.2248 estimated"),
        expect("standard_cost_value", standard and standard["amount_usd"] == 0.756),
    ]
    if all(ok):
        print("RESULT=COST_ESTIMATES_OK")
        return 0
    print("RESULT=COST_ESTIMATES_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
