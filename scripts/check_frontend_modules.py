from __future__ import annotations

from pathlib import Path
import re

from frontend_static_utils import read_static_js, static_js_files


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
ENTRY = PROJECT_ROOT / "app" / "static" / "app.js"
ENTRY_TEXT = ENTRY.read_text(encoding="utf-8")
STATIC_JS = read_static_js(PROJECT_ROOT)


def expect(name: str, condition: bool) -> bool:
    print(f"{name}={condition}")
    return bool(condition)


def main() -> int:
    print("=== Frontend module graph check ===")

    expected_modules = [
        "auto-refresh.js",
        "i18n.js",
        "navigation.js",
        "history-pagination.js",
        "history-rail.js",
        "model-constraints.js",
        "output-root.js",
        "reference-ui.js",
        "updates.js",
        "single-generation.js",
        "queue-form.js",
        "form-state.js",
        "shutdown.js",
    ]
    module_paths = static_js_files(PROJECT_ROOT)
    module_names = [path.name for path in module_paths]
    imports_resolve = True
    for path in module_paths:
        text = path.read_text(encoding="utf-8")
        for spec in re.findall(r'import\s+["\'](.+?)["\'];', text):
            module_path = spec.split("?", 1)[0]
            if spec.startswith(".") and not (path.parent / module_path).resolve().exists():
                imports_resolve = False

    checks = [
        expect("module_script_tag", '<script type="module" src="/static/app.js?v={{ static_asset_version }}"></script>' in TEMPLATE),
        expect("old_defer_script_absent", '<script src="/static/app.js" defer></script>' not in TEMPLATE),
        expect("module_import_cache_bust_present", "?v=20260709-video-only" in ENTRY_TEXT),
        expect(
            "entrypoint_is_import_map",
            all(f'./js/{name}' in ENTRY_TEXT for name in expected_modules if name != "reference-ui.js"),
        ),
        expect("expected_modules_exist", all((PROJECT_ROOT / "app" / "static" / "js" / name).exists() for name in expected_modules)),
        expect("text_to_audio_module_removed", "text-to-audio.js" not in ENTRY_TEXT and not (PROJECT_ROOT / "app" / "static" / "js" / "text-to-audio.js").exists()),
        expect("imports_resolve", imports_resolve),
        expect("entrypoint_stays_small", ENTRY.stat().st_size < 1000),
        expect("seedance_config_handoff_present", "window.seedanceConfig" in TEMPLATE and "modelCapabilities" in TEMPLATE),
        expect("static_asset_version_present", "static_asset_version" in TEMPLATE),
        expect("public_i18n_hook_present", "window.seedanceSetLanguage = setLanguage" in STATIC_JS),
        expect("public_tab_hook_present", "window.seedanceActivateTab = activateTab" in STATIC_JS),
        expect("public_pagination_hook_present", "window.seedanceInitHistoryPagination" in STATIC_JS),
        expect("public_model_hook_present", "window.seedanceSyncModelOptions" in STATIC_JS),
        expect("public_cost_hook_present", "window.seedanceUpdateCostEstimate" in STATIC_JS),
        expect("module_order_preserved", module_names[1:] == expected_modules),
    ]

    if all(checks):
        print("RESULT=FRONTEND_MODULES_OK")
        return 0

    print("module_files=" + repr([str(path) for path in module_paths]))
    print("RESULT=FRONTEND_MODULES_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
