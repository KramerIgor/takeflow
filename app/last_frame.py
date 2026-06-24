from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


@dataclass(frozen=True)
class LastFrameCandidate:
    url: str
    key_path: str
    score: int
    reason: str


def is_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    return value.startswith("http://") or value.startswith("https://")


def url_extension(url: str) -> str:
    parsed = urlparse(url)
    return Path(parsed.path).suffix.lower()


def is_video_url(url: str) -> bool:
    return url_extension(url) in VIDEO_EXTENSIONS


def is_image_url(url: str) -> bool:
    return url_extension(url) in IMAGE_EXTENSIONS


def score_candidate(key_path: str, url: str, parent: dict | None = None) -> tuple[int, str]:
    key_lower = key_path.lower()
    url_lower = url.lower()
    score = 0
    reasons: list[str] = []

    if "last_frame" in key_lower:
        score += 120
        reasons.append("key_contains_last_frame")

    if "last" in key_lower and "frame" in key_lower:
        score += 90
        reasons.append("key_contains_last_and_frame")

    if "output_images" in key_lower:
        score += 70
        reasons.append("key_contains_output_images")

    if "image_url" in key_lower:
        score += 65
        reasons.append("key_contains_image_url")

    if "images" in key_lower or ".image" in key_lower or "[image" in key_lower:
        score += 45
        reasons.append("key_contains_image")

    if "files" in key_lower:
        score += 20
        reasons.append("key_contains_files")

    if is_image_url(url):
        score += 50
        reasons.append("url_has_image_extension")

    if parent:
        content_type = str(parent.get("content_type") or parent.get("mime_type") or "").lower()
        file_name = str(parent.get("file_name") or parent.get("filename") or parent.get("name") or "").lower()

        if content_type.startswith("image/"):
            score += 80
            reasons.append("parent_content_type_image")

        if any(file_name.endswith(ext) for ext in IMAGE_EXTENSIONS):
            score += 45
            reasons.append("parent_file_name_image")

        if "last_frame" in file_name or ("last" in file_name and "frame" in file_name):
            score += 60
            reasons.append("parent_file_name_last_frame")

        if content_type.startswith("video/"):
            score -= 150
            reasons.append("parent_content_type_video")

    if is_video_url(url):
        score -= 200
        reasons.append("url_has_video_extension")

    if "video" in key_lower or "output.mp4" in url_lower:
        score -= 100
        reasons.append("looks_like_video_output")

    return score, ",".join(reasons) if reasons else "no_positive_reason"


def collect_last_frame_candidates(data: Any) -> list[LastFrameCandidate]:
    candidates: list[LastFrameCandidate] = []

    def walk(obj: Any, key_path: str = "", parent: dict | None = None) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                child_path = f"{key_path}.{key}" if key_path else str(key)

                if is_http_url(value):
                    score, reason = score_candidate(child_path, value, obj)

                    if score > 0 and not is_video_url(value):
                        candidates.append(
                            LastFrameCandidate(
                                url=value,
                                key_path=child_path,
                                score=score,
                                reason=reason,
                            )
                        )

                walk(value, child_path, obj)

        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                child_path = f"{key_path}[{index}]"
                walk(value, child_path, parent)

    walk(data)

    candidates.sort(key=lambda item: item.score, reverse=True)

    return candidates


def extract_last_frame_candidate(data: Any) -> LastFrameCandidate | None:
    candidates = collect_last_frame_candidates(data)

    if not candidates:
        return None

    return candidates[0]


def extract_last_frame_url(data: Any) -> str | None:
    candidate = extract_last_frame_candidate(data)

    if not candidate:
        return None

    return candidate.url


def last_frame_status_payload(data: Any) -> dict:
    candidate = extract_last_frame_candidate(data)

    if not candidate:
        return {
            "last_frame_found": False,
            "last_frame_url": None,
            "last_frame_key_path": None,
            "last_frame_source": None,
            "last_frame_candidate_score": None,
            "last_frame_candidate_reason": None,
        }

    return {
        "last_frame_found": True,
        "last_frame_url": candidate.url,
        "last_frame_key_path": candidate.key_path,
        "last_frame_source": "api",
        "last_frame_candidate_score": candidate.score,
        "last_frame_candidate_reason": candidate.reason,
    }
