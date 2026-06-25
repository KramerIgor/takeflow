from __future__ import annotations

from typing import Any


TEXT_IMAGE_RATES_USD_PER_SECOND: dict[str, dict[str, dict[str, float]]] = {
    "seedance-2.0": {
        "480p": {"16:9": 0.0703, "4:3": 0.0691, "1:1": 0.0672, "3:4": 0.0691, "9:16": 0.0703, "21:9": 0.0703},
        "720p": {"16:9": 0.1512, "4:3": 0.1522, "1:1": 0.1512, "3:4": 0.1522, "9:16": 0.1512, "21:9": 0.1519},
        "1080p": {"16:9": 0.34, "4:3": 0.34, "1:1": 0.34, "3:4": 0.34, "9:16": 0.34, "21:9": 0.34},
        "4k": {"16:9": 1.3721, "4:3": 1.3721, "1:1": 1.3721, "3:4": 1.3721, "9:16": 1.3721, "21:9": 1.3721},
    },
    "seedance-2.0-fast": {
        "480p": {"16:9": 0.0562, "4:3": 0.0553, "1:1": 0.0538, "3:4": 0.0553, "9:16": 0.0562, "21:9": 0.0562},
        "720p": {"16:9": 0.1210, "4:3": 0.1217, "1:1": 0.1210, "3:4": 0.1217, "9:16": 0.1210, "21:9": 0.1216},
    },
}

VIDEO_TYPICAL_RATES_USD_PER_SECOND: dict[str, dict[str, float]] = {
    "seedance-2.0": {"480p": 0.09, "720p": 0.19, "1080p": 0.41},
    "seedance-2.0-fast": {"480p": 0.06, "720p": 0.13},
}


def extract_cost_info(data: dict | None) -> dict | None:
    if not isinstance(data, dict):
        return None

    candidates = []

    def walk(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = str(key).lower()
                next_path = f"{path}.{key}" if path else str(key)
                if any(token in key_lower for token in ("cost", "price", "credit", "billing", "amount")):
                    if isinstance(value, (int, float, str)):
                        candidates.append({"key": next_path, "value": value})
                    elif isinstance(value, dict):
                        candidates.append({"key": next_path, "value": value})
                walk(value, next_path)
        elif isinstance(obj, list):
            for index, value in enumerate(obj):
                walk(value, f"{path}[{index}]")

    walk(data)
    if not candidates:
        return None

    return {"source": "segmind_response", "items": candidates[:8], "is_estimate": False}


def _normalize_duration(duration: Any) -> int | None:
    try:
        parsed = int(duration)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _has_reference_video(refs: list[dict] | None, reference_videos: list[str] | None = None) -> bool:
    if reference_videos:
        return True
    for ref in refs or []:
        if ref.get("media_type") == "video":
            return True
    return False


def estimate_seedance_cost_info(
    *,
    model: str | None,
    duration: Any,
    resolution: str | None,
    aspect_ratio: str | None,
    refs: list[dict] | None = None,
    reference_videos: list[str] | None = None,
) -> dict | None:
    normalized_model = str(model or "")
    normalized_resolution = str(resolution or "")
    normalized_aspect = str(aspect_ratio or "16:9")
    normalized_duration = _normalize_duration(duration)
    if not normalized_duration:
        return None

    input_mode = "video_to_video" if _has_reference_video(refs, reference_videos) else "text_or_image_to_video"

    rate = None
    if input_mode == "video_to_video":
        rate = VIDEO_TYPICAL_RATES_USD_PER_SECOND.get(normalized_model, {}).get(normalized_resolution)
    else:
        rates_by_resolution = TEXT_IMAGE_RATES_USD_PER_SECOND.get(normalized_model, {})
        rates_by_aspect = rates_by_resolution.get(normalized_resolution, {})
        rate = rates_by_aspect.get(normalized_aspect) or rates_by_aspect.get("16:9")

    if rate is None:
        return None

    amount = round(rate * normalized_duration, 4)
    return {
        "source": "segmind_pricing_estimate",
        "is_estimate": True,
        "amount_usd": amount,
        "rate_usd_per_second": rate,
        "duration_seconds": normalized_duration,
        "model": normalized_model,
        "resolution": normalized_resolution,
        "aspect_ratio": normalized_aspect,
        "input_mode": input_mode,
    }


def build_cost_info(
    response_data: dict | None,
    *,
    model: str | None,
    duration: Any,
    resolution: str | None,
    aspect_ratio: str | None,
    refs: list[dict] | None = None,
    reference_videos: list[str] | None = None,
) -> dict | None:
    return extract_cost_info(response_data) or estimate_seedance_cost_info(
        model=model,
        duration=duration,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        refs=refs,
        reference_videos=reference_videos,
    )


def cost_label(cost_info: dict | None) -> str | None:
    if not isinstance(cost_info, dict):
        return None

    if cost_info.get("source") == "segmind_pricing_estimate":
        amount = cost_info.get("amount_usd")
        if isinstance(amount, (int, float)):
            return f"~${amount:.4f} estimated"

    items = cost_info.get("items") or []
    if items:
        first = items[0]
        value = first.get("value")
        if isinstance(value, (int, float)):
            return f"${value:.4f}"
        if value:
            return str(value)

    amount = cost_info.get("amount_usd") or cost_info.get("cost")
    if isinstance(amount, (int, float)):
        return f"${amount:.4f}"
    if amount:
        return str(amount)

    return None
