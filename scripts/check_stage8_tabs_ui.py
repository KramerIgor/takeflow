from pathlib import Path
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import app.main as main
from scripts.frontend_static_utils import read_static_js


def render_index_html() -> str:
    template = main.templates.get_template("index.html")
    return template.render(main.base_context(request=None))


def main_run() -> int:
    print("=== App shell UI check ===")

    text = render_index_html()
    template_source = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    app_js = read_static_js(PROJECT_ROOT)
    css = (PROJECT_ROOT / "app" / "static" / "style.css").read_text(encoding="utf-8")

    sidebar_labels = [
        "Projects",
        "Single Generation",
        "Queue",
    ]
    tab_panels = [
        'data-tab-panel="project-settings"',
        'data-tab-panel="single-generation"',
        'data-tab-panel="queue-workflow"',
    ]
    expected_actions = [
        'formaction="/add-to-queue"',
        'formaction="/draft-task"',
        'action="/run-single-generation"',
        'action="/start-queue-loop"',
        'action="/batch-import"',
    ]
    removed_main_tab_labels = [
        "Continuation Chain",
    ]
    parked_future_tab_labels = [
        "Parallel Queues",
        "Cost Limits",
        "Text to Audio",
        "Текст в аудио",
    ]

    labels_ok = all(label in text for label in sidebar_labels)
    panels_ok = all(panel in text for panel in tab_panels)
    history_removed_ok = 'data-tab-target="single-history"' not in text and 'data-tab-panel="single-history"' not in text
    app_shell_ok = 'class="app-shell"' in text and 'class="app-sidebar"' in text and "sidebar-nav" in text
    single_history_rail_ok = (
        "single-history-rail" in text
        and 'data-history-rail-content="single"' in text
        and 'data-refresh-history="single"' in text
    )
    queue_history_rail_ok = (
        "queue-history-rail" in text
        and 'data-history-rail-content="queue"' in text
        and 'data-refresh-history="queue"' in text
    )
    compact_history_ok = (
        "compact-history-card" in template_source
        and "history_pagination" in template_source
        and "data-history-pagination" in template_source
        and "data-history-item" in template_source
    )
    css_layout_ok = "grid-template-columns: 210px minmax(0, 1fr)" in css and ".single-workspace" in css and ".single-history-panel" in css
    actions_ok = all(action in text for action in expected_actions)
    continuation_placeholder_ok = "Continuation Chain" not in text
    parked_tabs_hidden = all(label not in text for label in removed_main_tab_labels + parked_future_tab_labels)
    tab_storage_ok = "seedance_gui_active_tab_v1" in (text + app_js)
    form_names_ok = all(
        name in text
        for name in [
            'name="prompt"',
            'name="episode_name"',
            'name="scene_name"',
            'name="model"',
            'name="duration"',
            'name="resolution"',
            'name="aspect_ratio"',
            'name="seed"',
            'name="random_seed"',
            'name="generate_audio"',
            'name="return_last_frame"',
            'name="reference_files"',
        ]
    )
    text_to_audio_removed_ok = (
        'data-tab-target="text-to-audio"' not in text
        and 'data-tab-panel="text-to-audio"' not in text
        and 'action="/text-to-audio"' not in text
    )

    print("sidebar_labels_ok=", labels_ok, sep="")
    print("tab_panels_ok=", panels_ok, sep="")
    print("history_tab_removed=", history_removed_ok, sep="")
    print("app_shell_present=", app_shell_ok, sep="")
    print("single_history_rail_present=", single_history_rail_ok, sep="")
    print("queue_history_rail_present=", queue_history_rail_ok, sep="")
    print("compact_history_present=", compact_history_ok, sep="")
    print("css_layout_present=", css_layout_ok, sep="")
    print("existing_form_actions_ok=", actions_ok, sep="")
    print("continuation_placeholder_ok=", continuation_placeholder_ok, sep="")
    print("parked_tabs_hidden=", parked_tabs_hidden, sep="")
    print("tab_localstorage_ok=", tab_storage_ok, sep="")
    print("form_field_names_present=", form_names_ok, sep="")
    print("text_to_audio_removed=", text_to_audio_removed_ok, sep="")
    print("new_paid_submit_started=False")

    ok = (
        labels_ok
        and panels_ok
        and history_removed_ok
        and app_shell_ok
        and single_history_rail_ok
        and queue_history_rail_ok
        and compact_history_ok
        and css_layout_ok
        and actions_ok
        and continuation_placeholder_ok
        and parked_tabs_hidden
        and tab_storage_ok
        and form_names_ok
        and text_to_audio_removed_ok
    )

    if ok:
        print("RESULT=APP_SHELL_UI_OK")
        return 0

    print("RESULT=APP_SHELL_UI_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
