from __future__ import annotations

from pathlib import Path
import re
import unicodedata

from app import projects as projects_module


TAKE_RE = re.compile(r"_take_(\d{6})(?:$|\.mp4$)")
WINDOWS_FORBIDDEN_CHARS = '<>:"/\\|?*'


def sanitize_folder_part(value: str | None, fallback: str) -> str:
    name = unicodedata.normalize("NFKC", str(value or "").strip())

    for char in WINDOWS_FORBIDDEN_CHARS:
        name = name.replace(char, "_")

    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip(" .")

    if not name:
        return fallback

    return name[:80]


def normalize_episode_name(value: str | None) -> str:
    return sanitize_folder_part(value, "Episode_01")


def normalize_scene_name(value: str | None) -> str:
    return sanitize_folder_part(value, "Scene_001")


def project_dir(project_name: str | None = None) -> Path:
    if project_name:
        return projects_module.get_project_dir(project_name)

    return projects_module.get_active_project_dir()


def videos_root(project_name: str | None = None) -> Path:
    return project_dir(project_name=project_name) / "videos"


def runs_root(project_name: str | None = None) -> Path:
    return project_dir(project_name=project_name) / "runs"


def results_root(project_name: str | None = None) -> Path:
    # Backward-compatible alias for older code.
    return runs_root(project_name=project_name)


def take_prefix(episode_name: str | None = None, scene_name: str | None = None) -> str:
    episode = normalize_episode_name(episode_name)
    scene = normalize_scene_name(scene_name)
    return f"{episode}_{scene}_take_"


def take_stem(
    *,
    take_number: int,
    episode_name: str | None = None,
    scene_name: str | None = None,
) -> str:
    return f"{take_prefix(episode_name, scene_name)}{take_number:06d}"


def _extract_take_number(path: Path) -> int | None:
    match = TAKE_RE.search(path.name)

    if not match:
        return None

    return int(match.group(1))


def next_take_number(
    *,
    project_name: str | None = None,
    episode_name: str | None = None,
    scene_name: str | None = None,
) -> int:
    videos_dir = videos_root(project_name=project_name)
    runs_dir = runs_root(project_name=project_name)

    videos_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    prefix = take_prefix(episode_name, scene_name)
    max_number = 0

    for candidate in videos_dir.glob(f"{prefix}*.mp4"):
        number = _extract_take_number(candidate)
        if number is not None:
            max_number = max(max_number, number)

    for candidate in runs_dir.glob(f"{prefix}*"):
        if not candidate.is_dir():
            continue

        number = _extract_take_number(candidate)
        if number is not None:
            max_number = max(max_number, number)

    return max_number + 1


def allocate_take_paths(
    *,
    project_name: str | None = None,
    episode_name: str | None = None,
    scene_name: str | None = None,
) -> dict:
    videos_dir = videos_root(project_name=project_name)
    runs_dir = runs_root(project_name=project_name)

    videos_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    number = next_take_number(
        project_name=project_name,
        episode_name=episode_name,
        scene_name=scene_name,
    )

    stem = take_stem(
        take_number=number,
        episode_name=episode_name,
        scene_name=scene_name,
    )

    run_dir = runs_dir / stem
    run_dir.mkdir(parents=True, exist_ok=False)

    video_path = videos_dir / f"{stem}.mp4"

    return {
        "take_number": number,
        "take_stem": stem,
        "project_dir": str(project_dir(project_name=project_name)),
        "videos_dir": str(videos_dir),
        "runs_dir": str(runs_dir),
        "run_dir": str(run_dir),
        "video_path": str(video_path),
        "episode_name": normalize_episode_name(episode_name),
        "scene_name": normalize_scene_name(scene_name),
    }


def inbox_root(
    project_name: str | None = None,
    episode_name: str | None = None,
    scene_name: str | None = None,
) -> Path:
    # Backward-compatible alias for old tests/code.
    return runs_root(project_name=project_name)


def allocate_inbox_take_dir(
    project_name: str | None = None,
    episode_name: str | None = None,
    scene_name: str | None = None,
) -> Path:
    paths = allocate_take_paths(
        project_name=project_name,
        episode_name=episode_name,
        scene_name=scene_name,
    )

    return Path(paths["run_dir"])


def to_windows_path(path: str | Path) -> str:
    text = str(path)

    if text.startswith("/mnt/c/"):
        return "C:\\" + text[len("/mnt/c/"):].replace("/", "\\")

    if text.startswith("/mnt/d/"):
        return "D:\\" + text[len("/mnt/d/"):].replace("/", "\\")

    return text
