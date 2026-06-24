from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.segmind_client import SegmindClient


def main() -> int:
    client = SegmindClient()

    print("=== Polling method existence check ===")
    has_method = hasattr(client, "poll_request_until_done")
    print(f"poll_request_until_done={has_method}")

    print()
    print("=== Auth/status endpoint check, no generation ===")
    response = client.check_auth_without_generation()
    print(f"status_code={response.status_code}")
    print(f"url={response.url}")
    print("api_key=NOT_PRINTED")

    if has_method and response.status_code == 404:
        print("RESULT=STAGE_2_CLIENT_READY")
        return 0

    print("RESULT=CHECK_FAILED")
    print(response.text_preview)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
