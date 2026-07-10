from pathlib import Path
import re

from frontend_static_utils import read_static_js


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
APP_JS = read_static_js(PROJECT_ROOT)
CLIENT_TEXT = TEMPLATE + "\n" + APP_JS


def expect(name: str, condition: bool) -> bool:
    print(f"{name}={condition}")
    return bool(condition)


def translation_block(name: str) -> str:
    start = APP_JS.index(f"{name}: {{")
    next_name = "en" if name == "ru" else None
    if next_name:
        end = APP_JS.index(f"}},\n        {next_name}: {{", start)
    else:
        end = APP_JS.index("\n        }\n      };", start)
    return APP_JS[start:end]


def main() -> int:
    print("=== Frontend i18n/static UI check ===")

    ru_block = translation_block("ru")
    en_block = translation_block("en")
    data_i18n_keys = sorted(
        set(
            re.findall(r'data-i18n="([^"]+)"', TEMPLATE)
            + re.findall(r'data-i18n-placeholder="([^"]+)"', TEMPLATE)
            + re.findall(r'data-i18n-data-placeholder="([^"]+)"', TEMPLATE)
        )
    )
    missing_ru = [
        key
        for key in data_i18n_keys
        if "{{" not in key and f"{key}:" not in ru_block
    ]

    forbidden = [
        "Describe the anime",
        "anime video",
        "queue_history_hint",
        "История очереди использует",
        "Queue history uses compact cards",
        "technical id #",
        'onclick="return confirm',
    ]
    dynamic_en_keys = [
        "remove",
        "refreshing",
        "updated",
        "refresh_failed",
        "opening",
        "opened",
        "open_failed",
        "confirm_remove_queue",
        "confirm_switch_project",
        "confirm_delete_project",
        "confirm_create_queued_tasks",
        "confirm_stop_queue",
        "confirm_start_full_queue",
        "confirm_start_next_item",
        "estimated_generation_cost",
        "cost_estimate_unavailable",
        "cost_estimate_note",
        "cost_estimate_text_image",
        "cost_estimate_video",
        "run_as_single_paid",
        "unknown",
        "status_value_completed",
        "status_value_processing",
        "status_value_queued",
        "status_value_failed",
        "status_value_cancelled",
    ]

    checks = [
        expect("app_js_included", '<script type="module" src="/static/app.js?v={{ static_asset_version }}"></script>' in TEMPLATE),
        expect("prompt_placeholder_neutral", 'placeholder="Describe the video scene..."' in TEMPLATE),
        expect("prompt_placeholder_ru", 'placeholder_prompt: "Опишите видео-сцену..."' in APP_JS),
        expect("queue_empty_state_short", 'data-i18n="no_queue_history">No queued tasks yet.' in TEMPLATE),
        expect("no_forbidden_ui_copy", not any(item in CLIENT_TEXT for item in forbidden)),
        expect("status_display_layer_present", "data-status-value" in TEMPLATE and "statusLabel(" in APP_JS),
        expect("no_missing_ru_i18n_keys", not missing_ru),
        expect("dynamic_en_fallbacks_present", all(f"{key}:" in en_block for key in dynamic_en_keys)),
        expect("confirm_keys_on_paid_buttons", all(key in TEMPLATE for key in [
            'data-confirm-key="confirm_start_full_queue"',
            'data-confirm-key="confirm_start_next_item"',
            'data-confirm-key="confirm_remove_queue"',
        ])),
    ]

    if missing_ru:
        print("missing_ru_i18n_keys=" + repr(missing_ru))

    if all(checks):
        print("RESULT=FRONTEND_I18N_STATIC_OK")
        return 0

    print("RESULT=FRONTEND_I18N_STATIC_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
