from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.segmind_client import SegmindClient, SegmindConfigError


def main() -> int:
    try:
        client = SegmindClient()
        response = client.check_auth_without_generation()
    except SegmindConfigError as exc:
        print(f"CONFIG_ERROR: {exc}")
        return 2
    except Exception as exc:
        print(f"REQUEST_ERROR: {type(exc).__name__}: {exc}")
        return 3

    print("=== Segmind auth check ===")
    print(f"status_code={response.status_code}")
    print(f"url={response.url}")
    print("api_key=NOT_PRINTED")

    if response.status_code == 401:
        print("RESULT=AUTH_FAILED")
        print("DETAIL=Segmind rejected the API key.")
        return 1

    if response.status_code == 404:
        print("RESULT=AUTH_OK")
        print("DETAIL=API key was accepted; fake request id was not found, as expected.")
        return 0

    if response.status_code in (400, 422):
        print("RESULT=AUTH_PROBABLY_OK")
        print("DETAIL=API key was not rejected; endpoint returned validation-style response.")
        return 0

    print("RESULT=CHECK_UNCLEAR")
    print("DETAIL=Unexpected status. Response preview below.")
    print(response.text_preview)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
