from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import hashlib
import os
import threading
import time

import httpx

from app.version import APP_RELEASE_TAG, APP_VERSION, APP_VERSION_DISPLAY


DEFAULT_UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/IOKRAMER/takeflow/main/update.json"
UPDATE_MANIFEST_URL = os.getenv("TAKEFLOW_UPDATE_MANIFEST_URL", DEFAULT_UPDATE_MANIFEST_URL).strip()
UPDATE_TIMEOUT_SECONDS = 5.0


def _version_key(value: str) -> tuple[int, int, int, int]:
    normalized = (value or "").strip().lower().lstrip("v").replace("-", "")
    suffix_rank = 3
    if normalized.endswith("beta"):
        suffix_rank = 1
        normalized = normalized[:-4]
    elif normalized.endswith("alpha"):
        suffix_rank = 0
        normalized = normalized[:-5]
    elif normalized.endswith("rc"):
        suffix_rank = 2
        normalized = normalized[:-2]

    parts = [part for part in normalized.split(".") if part]
    nums = []
    for part in parts[:3]:
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits or "0"))
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2], suffix_rank


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    return _version_key(candidate) > _version_key(current)


@dataclass
class UpdateState:
    checked: bool = False
    checking: bool = False
    available: bool = False
    current_version: str = APP_VERSION
    current_display_version: str = APP_VERSION_DISPLAY
    current_tag: str = APP_RELEASE_TAG
    latest_version: str = ""
    latest_display_version: str = ""
    release_url: str = ""
    installer_url: str = ""
    sha256: str = ""
    manifest_url: str = UPDATE_MANIFEST_URL
    error: str = ""
    checked_at: float | None = None
    raw_manifest: dict = field(default_factory=dict)


@dataclass
class DownloadState:
    active: bool = False
    complete: bool = False
    error: str = ""
    bytes_downloaded: int = 0
    total_bytes: int | None = None
    percent: float | None = None
    path: str = ""
    url: str = ""
    sha256: str = ""
    started_at: float | None = None
    finished_at: float | None = None


class UpdateManager:
    def __init__(self, download_dir: Path):
        self.download_dir = download_dir
        self._lock = threading.Lock()
        self.update_state = UpdateState()
        self.download_state = DownloadState()

    def _state_dict(self) -> dict:
        return {
            "checked": self.update_state.checked,
            "checking": self.update_state.checking,
            "available": self.update_state.available,
            "current_version": self.update_state.current_version,
            "current_display_version": self.update_state.current_display_version,
            "current_tag": self.update_state.current_tag,
            "latest_version": self.update_state.latest_version,
            "latest_display_version": self.update_state.latest_display_version,
            "release_url": self.update_state.release_url,
            "installer_url": self.update_state.installer_url,
            "sha256": self.update_state.sha256,
            "manifest_url": self.update_state.manifest_url,
            "error": self.update_state.error,
            "checked_at": self.update_state.checked_at,
        }

    def get_update_state(self) -> dict:
        with self._lock:
            return self._state_dict()

    def get_download_state(self) -> dict:
        with self._lock:
            return {
                "active": self.download_state.active,
                "complete": self.download_state.complete,
                "error": self.download_state.error,
                "bytes_downloaded": self.download_state.bytes_downloaded,
                "total_bytes": self.download_state.total_bytes,
                "percent": self.download_state.percent,
                "path": self.download_state.path,
                "url": self.download_state.url,
                "started_at": self.download_state.started_at,
                "finished_at": self.download_state.finished_at,
            }

    def check_for_updates(self) -> dict:
        with self._lock:
            if not self.update_state.manifest_url:
                self.update_state.checked = True
                self.update_state.checking = False
                self.update_state.error = "Update manifest URL is not configured."
                self.update_state.checked_at = time.time()
                return self._state_dict()
            self.update_state.checking = True
            self.update_state.error = ""

        try:
            with httpx.Client(timeout=UPDATE_TIMEOUT_SECONDS, follow_redirects=True) as client:
                response = client.get(self.update_state.manifest_url)
                response.raise_for_status()
                manifest = response.json()

            latest_version = str(manifest.get("version") or manifest.get("latest_version") or "").strip()
            installer_url = str(manifest.get("installer_url") or "").strip()
            release_url = str(manifest.get("release_url") or "").strip()
            sha256 = str(manifest.get("sha256") or "").strip().lower()
            latest_display = str(manifest.get("display_version") or latest_version).strip()
            available = bool(latest_version and installer_url and is_newer_version(latest_version))

            with self._lock:
                self.update_state.checked = True
                self.update_state.checking = False
                self.update_state.available = available
                self.update_state.latest_version = latest_version
                self.update_state.latest_display_version = latest_display
                self.update_state.release_url = release_url
                self.update_state.installer_url = installer_url
                self.update_state.sha256 = sha256
                self.update_state.checked_at = time.time()
                self.update_state.raw_manifest = manifest if isinstance(manifest, dict) else {}
                return self._state_dict()
        except Exception as exc:
            with self._lock:
                self.update_state.checked = True
                self.update_state.checking = False
                self.update_state.available = False
                self.update_state.error = f"{type(exc).__name__}: {exc}"
                self.update_state.checked_at = time.time()
                return self._state_dict()

    def check_for_updates_background(self) -> None:
        thread = threading.Thread(target=self.check_for_updates, daemon=True)
        thread.start()

    def _installer_filename(self, installer_url: str) -> str:
        name = Path(urlparse(installer_url).path).name
        if not name.lower().endswith(".exe"):
            name = "TakeflowSetup.exe"
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)
        return safe or "TakeflowSetup.exe"

    def start_download_background(self) -> dict:
        with self._lock:
            if self.download_state.active:
                return {
                    "active": self.download_state.active,
                    "complete": self.download_state.complete,
                    "error": self.download_state.error,
                    "bytes_downloaded": self.download_state.bytes_downloaded,
                    "total_bytes": self.download_state.total_bytes,
                    "percent": self.download_state.percent,
                    "path": self.download_state.path,
                    "url": self.download_state.url,
                    "started_at": self.download_state.started_at,
                    "finished_at": self.download_state.finished_at,
                }
            if not self.update_state.available or not self.update_state.installer_url:
                raise ValueError("No update installer is available to download.")

            installer_url = self.update_state.installer_url
            sha256 = self.update_state.sha256
            path = self.download_dir / self._installer_filename(installer_url)
            self.download_state = DownloadState(
                active=True,
                complete=False,
                path=str(path),
                url=installer_url,
                sha256=sha256,
                started_at=time.time(),
            )

        thread = threading.Thread(target=self._download_installer, daemon=True)
        thread.start()
        return self.get_download_state()

    def _download_installer(self) -> None:
        state = self.get_download_state()
        url = state["url"]
        target = Path(state["path"])
        hasher = hashlib.sha256()

        try:
            self.download_dir.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(target.suffix + ".part")
            with httpx.stream("GET", url, timeout=None, follow_redirects=True) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length") or "0") or None
                with self._lock:
                    self.download_state.total_bytes = total

                with partial.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        if not chunk:
                            continue
                        handle.write(chunk)
                        hasher.update(chunk)
                        with self._lock:
                            self.download_state.bytes_downloaded += len(chunk)
                            if total:
                                self.download_state.percent = min(100.0, self.download_state.bytes_downloaded * 100 / total)

            digest = hasher.hexdigest()
            expected = state.get("sha256") or ""
            if expected and digest.lower() != expected.lower():
                raise ValueError("Downloaded installer checksum does not match update manifest.")

            partial.replace(target)
            with self._lock:
                self.download_state.active = False
                self.download_state.complete = True
                self.download_state.percent = 100.0
                self.download_state.finished_at = time.time()
        except Exception as exc:
            with self._lock:
                self.download_state.active = False
                self.download_state.complete = False
                self.download_state.error = f"{type(exc).__name__}: {exc}"
                self.download_state.finished_at = time.time()
