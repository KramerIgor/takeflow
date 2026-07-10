from __future__ import annotations

from pathlib import Path

from frontend_static_utils import read_static_js


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
MAIN_PY = (PROJECT_ROOT / "app" / "main.py").read_text(encoding="utf-8")
STATIC_JS = read_static_js(PROJECT_ROOT)
STYLE = (PROJECT_ROOT / "app" / "static" / "style.css").read_text(encoding="utf-8")


def expect(name: str, condition: bool) -> bool:
    print(f"{name}={condition}")
    return bool(condition)


def block_between(start_marker: str, end_marker: str) -> str:
    start = TEMPLATE.index(start_marker)
    end = TEMPLATE.index(end_marker, start)
    return TEMPLATE[start:end]


def main() -> int:
    print("=== Prompt reference and cost UI check ===")

    single_prompt = block_between('data-single-dropzone', '<div class="grid">')
    queue_prompt = block_between('data-queue-prompt-dropzone', '{% endif %}')
    retired_route = "n" + "ight-mode-preview"
    retired_context = "n" + "ight_mode_report"
    checks = [
        expect("single_refs_inside_prompt", "data-attached-refs" in single_prompt),
        expect("queue_refs_inside_prompt", "data-queue-attached-refs" in queue_prompt),
        expect("single_picker_inside_prompt", "data-trigger-reference-picker" in single_prompt),
        expect("queue_picker_inside_prompt", "data-trigger-queue-reference-picker" in queue_prompt),
        expect("single_rich_editor_inside_prompt", "data-prompt-rich-editor" in single_prompt),
        expect("queue_rich_editor_inside_prompt", "data-queue-prompt-rich-editor" in queue_prompt),
        expect("source_textareas_preserved", "data-prompt-source" in single_prompt and "data-prompt-source" in queue_prompt),
        expect("reference_counters_present", "data-reference-count" in single_prompt and "data-queue-reference-count" in queue_prompt),
        expect("hidden_file_inputs_preserved", "data-reference-files" in TEMPLATE and "data-queue-reference-files" in TEMPLATE),
        expect(
            "cost_card_present_in_form_macro",
            all(marker in TEMPLATE for marker in ["data-cost-estimate", "data-cost-estimate-value", "data-cost-estimate-note"]),
        ),
        expect(
            "cost_value_owned_by_estimator",
            'data-cost-estimate-value data-i18n' not in TEMPLATE
            and 'data-cost-estimate-note data-i18n' not in TEMPLATE,
        ),
        expect("pricing_maps_in_config", "text_image_rates" in MAIN_PY and "video_rates" in MAIN_PY),
        expect("client_cost_hook_present", "window.seedanceUpdateCostEstimate" in STATIC_JS),
        expect("cost_updates_on_refs", "seedance:refs-changed" in STATIC_JS and "hasVideoReference" in STATIC_JS),
        expect("media_token_menu_present", "renderReferenceTokenMenu" in STATIC_JS and "ref-token-option-title" in STYLE),
        expect(
            "reference_limit_model_aware",
            "reference_file_limit" in MAIN_PY
            and "referenceLimitForForm" in STATIC_JS
            and "prompt-ref-counter" in STYLE,
        ),
        expect("inline_reference_chips_present", "prompt-inline-ref" in STATIC_JS and "prompt-inline-ref" in STYLE),
        expect("bottom_token_preview_removed", "prompt-reference-tokens" not in TEMPLATE),
        expect("large_remove_buttons_removed", "ref-remove-button" in STYLE and 'remove.textContent = "×"' in STATIC_JS),
        expect("old_visual_reference_shell_removed", "attached-refs-shell" not in TEMPLATE),
        expect("retired_queue_preview_removed", retired_route not in TEMPLATE and retired_context not in MAIN_PY),
    ]

    if all(checks):
        print("RESULT=PROMPT_REFERENCE_COST_UI_OK")
        return 0

    print("RESULT=PROMPT_REFERENCE_COST_UI_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
