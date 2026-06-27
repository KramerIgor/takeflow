from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HTML = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")


def expect(name: str, condition: bool) -> bool:
    print(f"{name}={condition}")
    return bool(condition)


def slice_between(start: str, end: str) -> str:
    start_index = HTML.find(start)
    if start_index == -1:
        return ""
    end_index = HTML.find(end, start_index + len(start))
    if end_index == -1:
        return HTML[start_index:]
    return HTML[start_index:end_index]


def main() -> int:
    print("=== Drag/drop JS regression check ===")

    single_js = slice_between(
        'const form = document.querySelector(".single-generation-form")',
        'const form = document.querySelector(".queue-generation-form")',
    )
    queue_js = slice_between(
        'const form = document.querySelector(".queue-generation-form")',
        'const storageKey = "seedance_gui_form_preferences_v1"',
    )

    checks = [
        expect("single_js_found", bool(single_js)),
        expect("queue_js_found", bool(queue_js)),
        expect("single_has_dropzone", "data-single-dropzone" in HTML and 'dropzone.addEventListener("drop"' in single_js),
        expect("single_has_file_input_change", 'fileInput.addEventListener("change"' in single_js),
        expect("single_has_data_transfer_sync", "new DataTransfer()" in single_js),
        expect("single_has_no_queue_edit_scope", "setQueueEditMode" not in single_js and "cancelEditButton" not in single_js and "queue-edit-button" not in single_js),
        expect("queue_has_prompt_and_file_dropzones", "wireDropzone(promptDropzone)" in queue_js and "wireDropzone(fileDropzone)" in queue_js),
        expect("queue_has_edit_in_queue_handlers", "setQueueEditMode" in queue_js and "cancelEditButton.addEventListener" in queue_js and "queue-edit-button" in queue_js),
        expect("queue_has_update_route", "/update-queued-task/" in queue_js),
        expect("reference_accepts_media", "video/mp4" in HTML and "audio/mpeg" in HTML),
    ]

    if all(checks):
        print("RESULT=DRAGDROP_JS_REGRESSION_OK")
        return 0

    print("RESULT=DRAGDROP_JS_REGRESSION_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
