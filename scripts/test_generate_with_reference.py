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

    video = data.get("video")
    if isinstance(video, dict):
        value = video.get("url")
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
    client = SegmindClient(timeout=180.0)

    reference_path = Path("/mnt/c/AI_OUTPUT/Psailor_kun/api_tests/refs/reference_01.png")

    if not reference_path.exists():
        print(f"RESULT=REFERENCE_NOT_FOUND")
        print(f"reference_path={reference_path}")
        return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    take_dir = Path(OUTPUT_DIR) / "api_tests" / f"reference_image_{timestamp}"
    take_dir.mkdir(parents=True, exist_ok=True)

    prompt = (
        "A short 4-second cinematic test shot using image 1 as the main visual reference. "
        "Preserve the mood, color palette, and location feeling from image 1. "
        "Subtle camera push-in, gentle ambient motion, no text, no logos, clean video."
    )

    print("=== Uploading reference image to Segmind Storage ===")
    print(f"reference_path={reference_path}")
    print(f"reference_size_bytes={reference_path.stat().st_size}")
    print("api_key=NOT_PRINTED")

    upload_response = client.upload_asset(reference_path)
    (take_dir / "upload_response.json").write_text(
        json.dumps(upload_response.data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"upload_status_code={upload_response.status_code}")

    if not upload_response.ok:
        print("RESULT=UPLOAD_FAILED")
        print(upload_response.text_preview)
        return 2

    reference_url = client.extract_uploaded_asset_url(upload_response)

    if not reference_url:
        print("RESULT=NO_UPLOADED_URL")
        print("DETAIL=Upload succeeded but parser did not find an asset URL. Raw response saved to upload_response.json.")
        return 3

    print("uploaded_reference_url=URL_PRESENT_NOT_PRINTED")

    refs_manifest = {
        "reference_images": [
            {
                "role": "image 1",
                "local_path": str(reference_path),
                "uploaded_url": reference_url,
            }
        ]
    }

    (take_dir / "refs.json").write_text(
        json.dumps(refs_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = client.build_seedance_payload(
        prompt=prompt,
        reference_images=[reference_url],
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

    print()
    print("=== Reference image generation submit ===")
    print(f"take_dir={take_dir}")
    print("duration=4")
    print("resolution=480p")
    print("aspect_ratio=16:9")
    print("generate_audio=False")

    submit_started_at = time.time()
    submit_response = client.submit_seedance_async(payload)
    (take_dir / "submit_response.json").write_text(
        json.dumps(submit_response.data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"submit_status_code={submit_response.status_code}")

    if not submit_response.ok:
        print("RESULT=SUBMIT_FAILED")
        print(submit_response.text_preview)
        return 4

    request_id = client.extract_request_id(submit_response)
    print(f"request_id={request_id}")

    if not request_id:
        print("RESULT=NO_REQUEST_ID")
        print(submit_response.text_preview)
        return 5

    print()
    print("=== Polling ===")

    while True:
        status_response = client.get_request_status(request_id)
        status = client.extract_status(status_response)

        elapsed = int(time.time() - submit_started_at)
        print(f"{datetime.now().strftime('%H:%M:%S')} status_code={status_response.status_code} status={status} elapsed_seconds={elapsed}")

        (take_dir / "last_status.json").write_text(
            json.dumps(status_response.data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if status == "COMPLETED":
            break

        if status == "FAILED":
            print("RESULT=GENERATION_FAILED")
            print(status_response.text_preview)
            return 6

        if status_response.status_code == 401:
            print("RESULT=AUTH_FAILED")
            return 7

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
        return 8

    video_url = extract_output_url(result_response.data)

    if not video_url:
        print("RESULT=NO_VIDEO_URL_FOUND")
        print("Saved result_response.json for inspection.")
        return 9

    video_path = take_dir / "output.mp4"

    print("=== Downloading video ===")
    download_file(video_url, video_path)

    elapsed_total = int(time.time() - submit_started_at)

    summary = {
        "request_id": request_id,
        "elapsed_total_seconds": elapsed_total,
        "inference_time": None,
        "video_path": str(video_path),
        "video_size_bytes": video_path.stat().st_size,
    }

    if isinstance(result_response.data, dict):
        metrics = result_response.data.get("metrics")
        if isinstance(metrics, dict):
            summary["inference_time"] = metrics.get("inference_time")

    (take_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("RESULT=REFERENCE_GENERATION_OK")
    print(f"video_path={video_path}")
    print(f"video_size_bytes={video_path.stat().st_size}")
    print(f"elapsed_total_seconds={elapsed_total}")
    print(f"inference_time={summary['inference_time']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
