from pathlib import Path
import sys
import json
import time
from datetime import datetime

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.segmind_client import SegmindClient
from app.settings import OUTPUT_DIR


def extract_output_url(data):
    if not isinstance(data, dict):
        return None

    candidates = []

    for key in ("output", "video", "video_url", "url"):
        value = data.get(key)
        if isinstance(value, str):
            candidates.append(value)

    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if isinstance(item, str):
                candidates.append(item)
            elif isinstance(item, dict):
                for key in ("url", "video_url"):
                    value = item.get(key)
                    if isinstance(value, str):
                        candidates.append(value)

    if isinstance(output, dict):
        for key in ("url", "video_url"):
            value = output.get(key)
            if isinstance(value, str):
                candidates.append(value)

    for value in candidates:
        if value.startswith("http://") or value.startswith("https://"):
            return value

    return None


def download_file(url: str, path: Path) -> None:
    with httpx.stream("GET", url, timeout=300.0) as response:
        response.raise_for_status()
        with path.open("wb") as f:
            for chunk in response.iter_bytes():
                if chunk:
                    f.write(chunk)


def main() -> int:
    client = SegmindClient(timeout=120.0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    take_dir = Path(OUTPUT_DIR) / "api_tests" / f"text_only_{timestamp}"
    take_dir.mkdir(parents=True, exist_ok=True)

    prompt = (
        "A short 4-second cinematic anime test shot. "
        "A quiet Russian residential courtyard at golden hour, soft warm light, "
        "subtle camera push-in, no characters, no text, clean anime background art."
    )

    payload = client.build_seedance_payload(
        prompt=prompt,
        reference_images=[],
        reference_videos=[],
        reference_audios=[],
        duration=4,
        resolution="480p",
        aspect_ratio="16:9",
        generate_audio=False,
        seed=-1,
        return_last_frame=False,
    )

    (take_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (take_dir / "params.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("=== Test generation submit ===")
    print(f"take_dir={take_dir}")
    print("api_key=NOT_PRINTED")
    print("duration=4")
    print("resolution=480p")
    print("aspect_ratio=16:9")
    print("generate_audio=False")
    print()

    submit_response = client.submit_seedance_async(payload)
    (take_dir / "submit_response.json").write_text(
        json.dumps(submit_response.data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"submit_status_code={submit_response.status_code}")

    if not submit_response.ok:
        print("RESULT=SUBMIT_FAILED")
        print(submit_response.text_preview)
        return 1

    request_id = client.extract_request_id(submit_response)
    print(f"request_id={request_id}")

    if not request_id:
        print("RESULT=NO_REQUEST_ID")
        print(submit_response.text_preview)
        return 2

    print()
    print("=== Polling ===")

    while True:
        status_response = client.get_request_status(request_id)
        status = client.extract_status(status_response)

        print(f"{datetime.now().strftime('%H:%M:%S')} status_code={status_response.status_code} status={status}")

        (take_dir / "last_status.json").write_text(
            json.dumps(status_response.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if status == "COMPLETED":
            break

        if status == "FAILED":
            print("RESULT=GENERATION_FAILED")
            print(status_response.text_preview)
            return 3

        if status_response.status_code == 401:
            print("RESULT=AUTH_FAILED")
            return 4

        time.sleep(10)

    print()
    print("=== Getting result ===")

    result_response = client.get_request_result(request_id)
    (take_dir / "result_response.json").write_text(
        json.dumps(result_response.data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"result_status_code={result_response.status_code}")

    if not result_response.ok:
        print("RESULT=RESULT_FETCH_FAILED")
        print(result_response.text_preview)
        return 5

    video_url = extract_output_url(result_response.data)

    if not video_url:
        print("RESULT=NO_VIDEO_URL_FOUND")
        print("Saved result_response.json for inspection.")
        return 6

    video_path = take_dir / "output.mp4"

    print("=== Downloading video ===")
    download_file(video_url, video_path)

    print()
    print("RESULT=GENERATION_OK")
    print(f"video_path={video_path}")
    print(f"video_size_bytes={video_path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
