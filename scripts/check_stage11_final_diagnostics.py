"""Backward-compatible entrypoint for older Takeflow development instructions."""

from check_takeflow_release import main


if __name__ == "__main__":
    print("Deprecated: use scripts/check_takeflow_release.py")
    raise SystemExit(main())
