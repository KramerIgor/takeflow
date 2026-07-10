from __future__ import annotations

from pathlib import Path
import json
import tempfile
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.updater import UpdateManager, manifest_asset, runtime_asset_key


def expect(name: str, condition: bool) -> bool:
    print(f"{name}={bool(condition)}")
    return bool(condition)


def main() -> int:
    spec = (PROJECT_ROOT / "packaging" / "pyinstaller_takeflow_macos.spec").read_text(encoding="utf-8")
    build = (PROJECT_ROOT / "scripts" / "build_macos_dmg.sh").read_text(encoding="utf-8")
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "build-macos.yml").read_text(encoding="utf-8")
    runtime_paths = (PROJECT_ROOT / "app" / "runtime_paths.py").read_text(encoding="utf-8")
    main_py = (PROJECT_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    release_manifest = json.loads((PROJECT_ROOT / "update.json").read_text(encoding="utf-8-sig"))

    manifest = {
        "installer_url": "https://example.test/TakeflowSetup.exe",
        "sha256": "legacy",
        "assets": {
            "macos-arm64": {"url": "https://example.test/Takeflow-arm64.dmg", "sha256": "arm"},
            "macos-x64": {"url": "https://example.test/Takeflow-x64.dmg", "sha256": "intel"},
        },
    }
    with tempfile.TemporaryDirectory(prefix="takeflow_macos_release_") as temp_dir:
        manager = UpdateManager(Path(temp_dir), asset_key="macos-arm64")
        mac_filename = manager._installer_filename(manifest["assets"]["macos-arm64"]["url"])

    checks = [
        expect("asset_key_windows", runtime_asset_key("win32", "AMD64") == "windows-x64"),
        expect("asset_key_apple_silicon", runtime_asset_key("darwin", "arm64") == "macos-arm64"),
        expect("asset_key_intel", runtime_asset_key("darwin", "x86_64") == "macos-x64"),
        expect("manifest_selects_arm", manifest_asset(manifest, "macos-arm64").get("sha256") == "arm"),
        expect("manifest_selects_intel", manifest_asset(manifest, "macos-x64").get("sha256") == "intel"),
        expect("manifest_keeps_legacy_windows", manifest_asset(manifest, "windows-x64").get("sha256") == "legacy"),
        expect("release_manifest_has_windows", bool(manifest_asset(release_manifest, "windows-x64").get("url"))),
        expect("release_manifest_has_apple_silicon", bool(manifest_asset(release_manifest, "macos-arm64").get("url"))),
        expect("release_manifest_has_intel", bool(manifest_asset(release_manifest, "macos-x64").get("url"))),
        expect("mac_download_keeps_dmg", mac_filename == "Takeflow-arm64.dmg"),
        expect("mac_bundle_configured", "BUNDLE(" in spec and 'bundle_identifier="com.iokramer.takeflow"' in spec),
        expect("mac_bundle_is_background_app", '"LSUIElement": True' in spec),
        expect("mac_bundle_disables_upx", "upx=False" in spec),
        expect("dmg_has_applications_link", "ln -s /Applications" in build),
        expect("dmg_is_ad_hoc_signed", "codesign --force --deep --sign -" in build),
        expect("dmg_uses_hdiutil", "hdiutil create" in build),
        expect("workflow_builds_arm", "runner: macos-15" in workflow and "arch: arm64" in workflow),
        expect("workflow_builds_intel", "runner: macos-15-intel" in workflow and "arch: x86_64" in workflow),
        expect("workflow_smoke_tests_health", "http://127.0.0.1:7861/health" in workflow),
        expect("workflow_can_publish_release", "gh release upload" in workflow),
        expect("mac_runtime_uses_application_support", '"Application Support" / "Takeflow"' in runtime_paths),
        expect("mac_runtime_uses_library_logs", '"Library" / "Logs" / "Takeflow"' in runtime_paths),
        expect("finder_open_supported", '["open", "-R", str(target)]' in main_py),
        expect("dmg_launch_supported", '["open", str(installer_path)]' in main_py),
    ]

    if all(checks):
        print("RESULT=MACOS_RELEASE_OK")
        return 0
    print("RESULT=MACOS_RELEASE_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
