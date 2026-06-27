from __future__ import annotations

from dataclasses import dataclass
import base64
import mimetypes
from typing import Any
import time

from pathlib import Path

import httpx

from app.settings import SEGMIND_API_BASE, SEGMIND_API_KEY, SEGMIND_MODEL


class SegmindConfigError(RuntimeError):
    pass


class SegmindAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.data = data


@dataclass
class SegmindResponse:
    status_code: int
    ok: bool
    url: str
    data: Any
    text_preview: str


class SegmindClient:
    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else SEGMIND_API_KEY
        self.api_base = (api_base if api_base is not None else SEGMIND_API_BASE).rstrip("/")
        self.model = model if model is not None else SEGMIND_MODEL
        self.timeout = timeout

        if not self.api_key:
            raise SegmindConfigError("SEGMIND_API_KEY is empty. Set it in .env first.")

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _parse_response(self, response: httpx.Response) -> SegmindResponse:
        try:
            data: Any = response.json()
        except Exception:
            data = None

        text_preview = response.text[:1000] if response.text else ""

        return SegmindResponse(
            status_code=response.status_code,
            ok=response.is_success,
            url=str(response.url),
            data=data,
            text_preview=text_preview,
        )

    def _request(self, method: str, path: str, json_payload: dict[str, Any] | None = None) -> SegmindResponse:
        url = f"{self.api_base}{path}"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=json_payload,
            )

        return self._parse_response(response)

    def check_auth_without_generation(self) -> SegmindResponse:
        fake_request_id = "00000000-0000-0000-0000-000000000000"
        return self.get_request_status(fake_request_id)

    def get_user_credits(self) -> SegmindResponse:
        url = "https://api.segmind.com/v1/get-user-credits"
        headers = {
            "x-api-key": self.api_key,
            "accept": "application/json",
        }

        with httpx.Client(timeout=min(self.timeout, 8.0)) as client:
            response = client.get(url, headers=headers)

        return self._parse_response(response)


    def upload_asset(self, file_path: str | Path) -> SegmindResponse:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Asset file not found: {path}")

        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type:
            suffix = path.suffix.lower()
            if suffix in (".jpg", ".jpeg"):
                mime_type = "image/jpeg"
            elif suffix == ".png":
                mime_type = "image/png"
            elif suffix == ".webp":
                mime_type = "image/webp"
            else:
                mime_type = "application/octet-stream"

        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        data_url = f"data:{mime_type};base64,{encoded}"

        url = "https://workflows-api.segmind.com/upload-asset"
        headers = {
            "x-api-key": self.api_key,
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
        }

        timeout = httpx.Timeout(
            connect=30.0,
            read=max(float(self.timeout), 300.0),
            write=max(float(self.timeout), 600.0),
            pool=30.0,
        )
        last_timeout: httpx.TimeoutException | None = None
        for attempt in range(1, 4):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, headers=headers, json={"data_urls": [data_url]})
                return self._parse_response(response)
            except httpx.TimeoutException as exc:
                last_timeout = exc
                if attempt == 3:
                    raise
                time.sleep(2 * attempt)

        raise last_timeout or TimeoutError("Reference upload timed out.")

    @staticmethod
    def extract_uploaded_asset_url(response: SegmindResponse) -> str | None:
        if not isinstance(response.data, dict):
            return None

        for key in ("urls", "file_urls"):
            urls = response.data.get(key)
            if isinstance(urls, list) and urls:
                first = urls[0]
                if isinstance(first, str) and first.startswith(("http://", "https://")):
                    return first

        files = response.data.get("files")
        if isinstance(files, list) and files:
            first_file = files[0]
            if isinstance(first_file, dict):
                for key in ("url", "file_url"):
                    value = first_file.get(key)
                    if isinstance(value, str) and value.startswith(("http://", "https://")):
                        return value

        return None

    def submit_seedance_async(self, payload: dict[str, Any]) -> SegmindResponse:
        return self._request("POST", f"/v2/{self.model}", json_payload=payload)

    def get_request_status(self, request_id: str) -> SegmindResponse:
        return self._request("GET", f"/v2/requests/{request_id}/status")

    def get_request_result(self, request_id: str) -> SegmindResponse:
        return self._request("GET", f"/v2/requests/{request_id}")

    def poll_request_until_done(
        self,
        request_id: str,
        poll_interval_seconds: int = 10,
        timeout_seconds: int = 1800,
    ) -> SegmindResponse:
        started_at = time.time()
        last_response: SegmindResponse | None = None

        while True:
            response = self.get_request_status(request_id)
            last_response = response
            status = self.extract_status(response)

            if status in ("COMPLETED", "FAILED"):
                return response

            if response.status_code == 401:
                return response

            elapsed = time.time() - started_at
            if elapsed >= timeout_seconds:
                raise TimeoutError(
                    f"Segmind request polling timed out after {timeout_seconds} seconds. "
                    f"Last status={status}, status_code={response.status_code}"
                )

            time.sleep(poll_interval_seconds)

    @staticmethod
    def extract_request_id(response: SegmindResponse) -> str | None:
        if not isinstance(response.data, dict):
            return None

        for key in ("request_id", "id", "requestId"):
            value = response.data.get(key)
            if isinstance(value, str) and value:
                return value

        return None

    @staticmethod
    def extract_status(response: SegmindResponse) -> str | None:
        if not isinstance(response.data, dict):
            return None

        for key in ("status", "state"):
            value = response.data.get(key)
            if isinstance(value, str) and value:
                return value.upper()

        return None

    @staticmethod
    def build_seedance_payload(
        prompt: str,
        reference_images: list[str] | None = None,
        reference_videos: list[str] | None = None,
        reference_audios: list[str] | None = None,
        duration: int = 4,
        resolution: str = "480p",
        aspect_ratio: str = "16:9",
        generate_audio: bool = False,
        seed: int = -1,
        return_last_frame: bool = False,
    ) -> dict[str, Any]:
        return {
            "prompt": prompt,
            "reference_images": reference_images or [],
            "reference_videos": reference_videos or [],
            "reference_audios": reference_audios or [],
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "generate_audio": generate_audio,
            "seed": seed,
            "return_last_frame": return_last_frame,
            "skip_moderation": False,
        }
