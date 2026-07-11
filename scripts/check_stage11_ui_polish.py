"""Backward-compatible entrypoint for older Takeflow development instructions."""

from check_ui_quality import main


if __name__ == "__main__":
    print("Deprecated: use scripts/check_ui_quality.py")
    raise SystemExit(main())
