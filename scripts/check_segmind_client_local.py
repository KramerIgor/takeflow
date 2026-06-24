from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.segmind_client import SegmindClient


def main() -> int:
    client = SegmindClient()

    print("=== Local client construction ===")
    print(f"model={client.model}")
    print(f"api_base={client.api_base}")
    print("api_key=NOT_PRINTED")
    print()

    print("=== Payload builder check ===")
    payload = client.build_seedance_payload(
        prompt="Test prompt only. Do not submit in this script.",
        duration=4,
        resolution="480p",
        aspect_ratio="16:9",
        generate_audio=False,
        seed=-1,
        return_last_frame=False,
    )
    safe_payload = dict(payload)
    print(json.dumps(safe_payload, indent=2, ensure_ascii=False))
    print()

    print("=== Auth/status endpoint check with fake request id ===")
    response = client.check_auth_without_generation()
    print(f"status_code={response.status_code}")
    print(f"url={response.url}")
    print("api_key=NOT_PRINTED")

    if response.status_code == 404:
        print("RESULT=CLIENT_OK_AUTH_OK")
        print("DETAIL=Client methods work; API key accepted; fake request id not found as expected.")
        return 0

    if response.status_code == 401:
        print("RESULT=AUTH_FAILED")
        print("DETAIL=Segmind rejected the API key.")
        return 1

    print("RESULT=CHECK_UNCLEAR")
    print("DETAIL=Unexpected response preview:")
    print(response.text_preview)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
