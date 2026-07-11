from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.last_frame import (
    collect_last_frame_candidates,
    extract_last_frame_url,
    last_frame_status_payload,
)


def assert_equal(name: str, actual, expected) -> bool:
    ok = actual == expected
    print(f"{name}={ok}")

    if not ok:
        print(f"{name}_actual={actual}")
        print(f"{name}_expected={expected}")

    return ok


def main() -> int:
    print("=== Last-frame extractor smoke test ===")

    cases = [
        (
            "direct_last_frame_url",
            {"last_frame_url": "https://example.com/last.png"},
            "https://example.com/last.png",
        ),
        (
            "nested_last_frame_url",
            {"last_frame": {"url": "https://example.com/last.jpg"}},
            "https://example.com/last.jpg",
        ),
        (
            "output_images",
            {"output_images": [{"url": "https://example.com/frame.webp"}]},
            "https://example.com/frame.webp",
        ),
        (
            "files_image_beats_video",
            {
                "files": [
                    {"url": "https://example.com/output.mp4", "content_type": "video/mp4"},
                    {"url": "https://example.com/final-frame.png", "content_type": "image/png"},
                ]
            },
            "https://example.com/final-frame.png",
        ),
        (
            "video_only_returns_none",
            {"output": "https://example.com/output.mp4", "video": {"url": "https://example.com/output.mp4"}},
            None,
        ),
    ]

    checks = []

    for name, payload, expected in cases:
        actual = extract_last_frame_url(payload)
        checks.append(assert_equal(name, actual, expected))

        status = last_frame_status_payload(payload)
        print(f"{name}_status_last_frame_found={status['last_frame_found']}")

    old_result_candidates_ok = True
    old_result_path = Path("/mnt/c/AI_OUTPUT/Example_project/api_tests/text_only_20260620_090301/result_response.json")

    if old_result_path.exists():
        old_payload = json.loads(old_result_path.read_text(encoding="utf-8"))
        old_candidates = collect_last_frame_candidates(old_payload)
        old_url = extract_last_frame_url(old_payload)

        print("old_video_only_result_checked=True")
        print("old_video_only_candidates_count=", len(old_candidates), sep="")
        print("old_video_only_last_frame_url=", old_url, sep="")

        old_result_candidates_ok = old_url is None
    else:
        print("old_video_only_result_checked=False")

    checks.append(assert_equal("old_video_only_response_returns_none", old_result_candidates_ok, True))

    print("new_paid_submit_started=False")

    if all(checks):
        print("RESULT=LAST_FRAME_EXTRACTOR_OK")
        return 0

    print("RESULT=LAST_FRAME_EXTRACTOR_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
