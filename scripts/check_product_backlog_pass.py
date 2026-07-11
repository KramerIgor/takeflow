from __future__ import annotations

import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import settings
from app.segmind_client import SegmindClient, SegmindResponse


TEMPLATE = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
MAIN = (PROJECT_ROOT / "app" / "main.py").read_text(encoding="utf-8")
APP_JS = (PROJECT_ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
I18N_JS = (PROJECT_ROOT / "app" / "static" / "js" / "i18n.js").read_text(encoding="utf-8")
HISTORY_JS = (PROJECT_ROOT / "app" / "static" / "js" / "history-rail.js").read_text(encoding="utf-8")
AUTO_JS = (PROJECT_ROOT / "app" / "static" / "js" / "auto-refresh.js").read_text(encoding="utf-8")
QUEUE_JS = (PROJECT_ROOT / "app" / "static" / "js" / "queue-controls.js").read_text(encoding="utf-8")
REFERENCE_JS = (PROJECT_ROOT / "app" / "static" / "js" / "reference-ui.js").read_text(encoding="utf-8")
SEED_JS = (PROJECT_ROOT / "app" / "static" / "js" / "seed-control.js").read_text(encoding="utf-8")
WORKER = (PROJECT_ROOT / "app" / "queue_worker.py").read_text(encoding="utf-8")
RECOVERY = (PROJECT_ROOT / "app" / "task_recovery.py").read_text(encoding="utf-8")


def check(name: str, condition: bool) -> bool:
    print(f"{name}={bool(condition)}")
    return bool(condition)


def main() -> int:
    header_seed = SegmindClient.extract_seed(
        SegmindResponse(200, True, "https://example.test", {}, "", {"x-segmind-seed": "123456"})
    )
    body_seed = SegmindClient.extract_seed(
        SegmindResponse(200, True, "https://example.test", {"metadata": {"actual_seed": 654321}}, "")
    )
    boolean_seed = SegmindClient.extract_seed(
        SegmindResponse(200, True, "https://example.test", {"seed": -1, "random_seed": True}, "")
    )

    previous_key = settings.get_segmind_api_key()
    previous_base = settings.get_segmind_api_base()
    try:
        settings.apply_runtime_segmind_settings(api_key="runtime-test-key", api_base="https://runtime.example/")
        runtime_client = SegmindClient()
        runtime_applies = runtime_client.api_key == "runtime-test-key" and runtime_client.api_base == "https://runtime.example"
    finally:
        settings.apply_runtime_segmind_settings(api_key=previous_key, api_base=previous_base)
        if not previous_key:
            os.environ.pop("SEGMIND_API_KEY", None)

    queue_actions_index = TEMPLATE.index("compact-history-actions")
    details_index = TEMPLATE.index('class="history-details"', queue_actions_index)
    queue_edit_index = TEMPLATE.index("queue-edit-button", queue_actions_index)

    checks = [
        check("short_model_labels", all(label in MAIN for label in ["Seedance 2.0 Pro", "Seedance 2.0 Fast", "Seedance 2.0 Mini"])),
        check("old_model_notes_removed", all(note not in MAIN + TEMPLATE for note in ["Base model / 4K", "Draft tier / 480p-720p", "Legacy faster / cheaper variant"])),
        check("default_model_setting_removed", 'name="default_model"' not in TEMPLATE and "api_restart_hint" not in TEMPLATE),
        check("api_settings_apply_runtime", runtime_applies and "apply_runtime_segmind_settings" in MAIN),
        check("random_seed_default", 'data-random-seed checked' in TEMPLATE and "seedanceApplySeedState" in SEED_JS),
        check("audio_default", 'name="generate_audio" value="1" checked' in TEMPLATE),
        check("actual_seed_from_header", header_seed == 123456),
        check("actual_seed_from_body", body_seed == 654321),
        check("seed_boolean_not_misread", boolean_seed is None),
        check("actual_seed_persisted", all("actual_seed" in text and "update_task_params" in text for text in [WORKER, RECOVERY])),
        check("targeted_history_refresh", "card.replaceWith(replacement)" in HISTORY_JS and "seedanceRefreshProcessingHistoryCards" in AUTO_JS),
        check("auto_refresh_does_not_replace_rail", "railPanel.innerHTML" not in AUTO_JS and "seedanceRefreshHistoryRail" not in AUTO_JS),
        check("localized_card_patch", "seedanceLocalizeRoot(replacement, lang)" in HISTORY_JS and "window.seedanceLocalizeRoot" in I18N_JS),
        check("queue_actions_outside_details", queue_actions_index < queue_edit_index < details_index),
        check("queued_run_as_single_removed", "Run as Single (paid)" not in TEMPLATE),
        check("run_next_ui_removed", "Start Next Item (paid)" not in TEMPLATE and "Run only next item" not in TEMPLATE),
        check("batch_import_moves_under_controls", "insertAdjacentElement(\"afterend\", batchImportPanel)" in QUEUE_JS),
        check("flash_is_transient", "data-flash-notice" in TEMPLATE and "flash-notice.js" in APP_JS and "seedance:tab-changed" in APP_JS + I18N_JS + (PROJECT_ROOT / "app" / "static" / "js" / "navigation.js").read_text(encoding="utf-8")),
        check("clipboard_files_become_references", "referenceFilesFromClipboard" in REFERENCE_JS and "screenshot-" in REFERENCE_JS),
        check("failed_actions_are_clear", all(value in TEMPLATE for value in ["send_again", "add_to_queue_again", "delete_error_record", "/delete-failed-task/"])),
        check("friendly_error_display", "generation_error_connection" in MAIN and "error_display_key" in TEMPLATE and "technical_error" in TEMPLATE),
    ]

    if all(checks):
        print("RESULT=PRODUCT_BACKLOG_PASS_OK")
        return 0
    print("RESULT=PRODUCT_BACKLOG_PASS_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
