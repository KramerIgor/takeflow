from pathlib import Path
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import app.main as main


def render_index_html() -> str:
    template = main.templates.get_template("index.html")
    return template.render(main.base_context(request=None))


def main_run() -> int:
    print("=== Stage 8 tabbed UI check ===")

    text = render_index_html()

    tab_labels = [
        "Projects",
        "Single Generation",
        "History",
        "Queue",
    ]
    tab_panels = [
        'data-tab-panel="project-settings"',
        'data-tab-panel="single-generation"',
        'data-tab-panel="single-history"',
        'data-tab-panel="queue-workflow"',
    ]
    expected_actions = [
        'formaction="/add-to-queue"',
        'formaction="/draft-task"',
        'action="/run-single-generation"',
        'action="/start-queue-once"',
        'action="/start-queue-loop"',
        'action="/batch-import"',
    ]
    removed_main_tab_labels = [
        "Continuation Chain",
    ]
    parked_future_tab_labels = [
        "Parallel Queues",
        "Cost Limits",
    ]

    labels_ok = all(label in text for label in tab_labels)
    panels_ok = all(panel in text for panel in tab_panels)
    actions_ok = all(action in text for action in expected_actions)
    continuation_placeholder_ok = "Continuation Chain" not in text
    parked_tabs_hidden = all(label not in text for label in removed_main_tab_labels + parked_future_tab_labels)
    tab_storage_ok = "seedance_gui_active_tab_v1" in text
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
            'name="generate_audio"',
            'name="return_last_frame"',
            'name="reference_images"',
        ]
    )

    print("tab_labels_ok=", labels_ok, sep="")
    print("tab_panels_ok=", panels_ok, sep="")
    print("existing_form_actions_ok=", actions_ok, sep="")
    print("continuation_placeholder_ok=", continuation_placeholder_ok, sep="")
    print("parked_tabs_hidden=", parked_tabs_hidden, sep="")
    print("tab_localstorage_ok=", tab_storage_ok, sep="")
    print("form_field_names_present=", form_names_ok, sep="")
    print("new_paid_submit_started=False")

    ok = (
        labels_ok
        and panels_ok
        and actions_ok
        and continuation_placeholder_ok
        and parked_tabs_hidden
        and tab_storage_ok
        and form_names_ok
    )

    if ok:
        print("RESULT=STAGE8_TABBED_UI_OK")
        return 0

    print("RESULT=STAGE8_TABBED_UI_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main_run())
