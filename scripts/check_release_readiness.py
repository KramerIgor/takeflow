from __future__ import annotations

from pathlib import Path
import os
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["TAKEFLOW_UPDATE_MANIFEST_URL"] = ""

from fastapi.testclient import TestClient

from app.main import app
from app.version import APP_RELEASE_TAG, APP_VERSION, APP_VERSION_DISPLAY


def expect(name: str, condition: bool) -> bool:
    print(f"{name}={condition}")
    return bool(condition)


def public_source_text() -> str:
    roots = ["app", "data/examples", "docs", "scripts", ".agents"]
    suffixes = {".css", ".csv", ".html", ".js", ".json", ".md", ".ps1", ".py", ".sh", ".txt"}
    parts: list[str] = []
    for root in roots:
        for path in (PROJECT_ROOT / root).rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes:
                parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    for name in ("AGENTS.md", "README.md", "README_RU.md", ".env.example"):
        parts.append((PROJECT_ROOT / name).read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def main() -> int:
    print("=== Release readiness check ===")

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    readme_ru = (PROJECT_ROOT / "README_RU.md").read_text(encoding="utf-8")
    user_guide = (PROJECT_ROOT / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")
    user_guide_ru = (PROJECT_ROOT / "docs" / "USER_GUIDE_RU.md").read_text(encoding="utf-8")
    macos_guide = (PROJECT_ROOT / "docs" / "MACOS_USER_GUIDE.md").read_text(encoding="utf-8")
    macos_guide_ru = (PROJECT_ROOT / "docs" / "MACOS_USER_GUIDE_RU.md").read_text(encoding="utf-8")
    agent_guide = (PROJECT_ROOT / "docs" / "AGENT_GUIDE.md").read_text(encoding="utf-8")
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    inno = (PROJECT_ROOT / "packaging" / "Takeflow.iss").read_text(encoding="utf-8")
    build_script = (PROJECT_ROOT / "scripts" / "build_windows_installer.ps1").read_text(encoding="utf-8")
    app_js = (PROJECT_ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    updates_js = (PROJECT_ROOT / "app" / "static" / "js" / "updates.js").read_text(encoding="utf-8")
    public_sources = public_source_text().lower()

    with TestClient(app) as client:
        page = client.get("/")
        health = client.get("/health")
        update_status = client.get("/update-status")
        download_status = client.get("/update-download/status")

    checks = [
        expect("version_constant_ok", APP_VERSION == "0.1.1beta"),
        expect("release_tag_ok", APP_RELEASE_TAG == "v0.1.1-beta"),
        expect("version_display_in_header", f"v{APP_VERSION_DISPLAY}" in page.text),
        expect("version_in_health", health.json().get("version") == APP_VERSION),
        expect("shutdown_button_present", "data-shutdown-server" in page.text),
        expect("shutdown_token_in_config", "shutdownToken" in page.text),
        expect("update_panel_present", "data-update-panel" in page.text),
        expect("compact_header_updater_present", 'class="release-status"' in template),
        expect("legacy_update_notice_absent", "update-notice" not in template),
        expect("raw_update_error_hidden", '+ state.error' not in updates_js and '${state.error}' not in updates_js),
        expect("public_repo_urls_current", "KramerIgor/takeflow" in readme and "KramerIgor/takeflow" in build_script),
        expect("update_status_endpoint_ok", update_status.status_code == 200),
        expect("download_status_endpoint_ok", download_status.status_code == 200),
        expect("launcher_exists", (PROJECT_ROOT / "takeflow_launcher.py").exists()),
        expect("pyinstaller_spec_exists", (PROJECT_ROOT / "packaging" / "pyinstaller_takeflow.spec").exists()),
        expect("macos_pyinstaller_spec_exists", (PROJECT_ROOT / "packaging" / "pyinstaller_takeflow_macos.spec").exists()),
        expect("macos_build_script_exists", (PROJECT_ROOT / "scripts" / "build_macos_dmg.sh").exists()),
        expect("macos_workflow_exists", (PROJECT_ROOT / ".github" / "workflows" / "build-macos.yml").exists()),
        expect("inno_script_exists", "[Setup]" in inno and "DefaultDirName={localappdata}\\Takeflow" in inno),
        expect("installer_creates_shortcuts", "{autodesktop}" in inno and "{group}\\{#MyAppName}" in inno),
        expect("inno_does_not_package_env", ".env" not in inno),
        expect("build_script_reads_app_version", "from app.version import APP_VERSION" in build_script),
        expect("update_manifest_exists", (PROJECT_ROOT / "update.json").exists()),
        expect("gitignore_excludes_secrets", ".env" in gitignore and ".venv/" in gitignore and ".runtime/" in gitignore),
        expect("gitignore_excludes_update_downloads", "data/updates/" in gitignore and "*.part" in gitignore),
        expect("personal_project_identifier_absent", ("psai" + "lor") not in public_sources),
        expect("frontend_update_shutdown_modules", "updates.js" in app_js and "shutdown.js" in app_js),
        expect("readme_mentions_installer", "Windows Installer" in readme and "GitHub Releases" in readme),
        expect("readme_language_switch", "[Русский](README_RU.md)" in readme and "[English](README.md)" in readme_ru),
        expect("russian_readme_complete", "Скачать для Windows" in readme_ru and "Скачать для macOS" in readme_ru and "Безопасность и приватность" in readme_ru),
        expect("user_guides_present", "Takeflow User Guide" in user_guide and "Руководство пользователя Takeflow" in user_guide_ru),
        expect("macos_guides_bilingual", "Takeflow for macOS" in macos_guide and "Takeflow для macOS" in macos_guide_ru),
        expect("agent_guide_present", "Takeflow Agent and Contributor Guide" in agent_guide and "Safety Rules" in agent_guide),
    ]

    if all(checks):
        print("RESULT=RELEASE_READINESS_OK")
        return 0

    print("RESULT=RELEASE_READINESS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
