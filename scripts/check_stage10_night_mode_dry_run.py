import os
import sys
from types import SimpleNamespace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("PYTHON_DOTENV_DISABLED", "1")

import app.main as main


def assert_true(name: str, condition: bool) -> None:
    print(f"{name}={condition}")
    if not condition:
        raise AssertionError(name)


def fake_tasks() -> list[dict]:
    return [
        {
            "id": 10,
            "status": "completed",
            "model": "seedance-2.0-fast",
            "prompt": "completed parent",
            "params": {"episode_name": "Episode_01", "scene_name": "Scene_001"},
        },
        {
            "id": 11,
            "status": "queued",
            "model": "seedance-2.0-fast",
            "prompt": "first queued independent",
            "params": {"episode_name": "Episode_01", "scene_name": "Scene_002"},
        },
        {
            "id": 12,
            "status": "queued",
            "model": "seedance-2.0-fast",
            "prompt": "child of completed parent",
            "params": {
                "episode_name": "Episode_01",
                "scene_name": "Scene_002",
                "continuation_mode": "last_frame_as_reference",
                "parent_task_id": 10,
            },
        },
        {
            "id": 13,
            "status": "queued",
            "model": "seedance-2.0-fast",
            "prompt": "child of selected parent",
            "params": {
                "episode_name": "Episode_01",
                "scene_name": "Scene_002",
                "continuation_mode": "last_frame_as_reference",
                "parent_task_id": 12,
            },
        },
        {
            "id": 14,
            "status": "queued",
            "model": "seedance-2.0-fast",
            "prompt": "blocked child",
            "params": {
                "episode_name": "Episode_01",
                "scene_name": "Scene_003",
                "continuation_mode": "last_frame_as_reference",
                "parent_task_id": 999,
            },
        },
    ]


def check_helper_plan() -> None:
    report = main.build_night_mode_preview_plan(
        max_tasks=3,
        stop_on_consecutive_errors=2,
        tasks=fake_tasks(),
    )

    assert_true("helper_status_preview", report["status"] == "preview")
    assert_true("helper_queued_count", report["queued_count"] == 4)
    assert_true("helper_selected_count_respects_max_tasks", report["selected_count"] == 3)
    assert_true("helper_stop_on_consecutive_errors", report["stop_on_consecutive_errors"] == 2)
    assert_true("helper_dependent_count", report["dependent_continuation_count"] == 2)
    assert_true("helper_no_blocked_parent_in_selected_chain", report["blocked_by_parent_count"] == 0)
    assert_true(
        "helper_no_parallel_dependent_continuation_chains",
        report["no_parallel_dependent_continuation_chains"] is True,
    )
    assert_true("helper_new_paid_submit_started_false", report["new_paid_submit_started"] is False)

    blocked_report = main.build_night_mode_preview_plan(
        max_tasks=4,
        stop_on_consecutive_errors=1,
        tasks=fake_tasks(),
    )
    assert_true("helper_blocked_parent_detected", blocked_report["blocked_by_parent_count"] == 1)


def check_route_preview() -> None:
    original_list_tasks = main.list_tasks
    original_base_context = main.base_context
    original_template_response = main.templates.TemplateResponse

    captured = {}

    def fake_list_tasks(limit=1000):
        return fake_tasks()

    def fake_base_context(request, **kwargs):
        captured.update(kwargs)
        return {"request": request, **kwargs}

    def fake_template_response(template_name, context):
        return SimpleNamespace(template_name=template_name, context=context)

    try:
        main.list_tasks = fake_list_tasks
        main.base_context = fake_base_context
        main.templates.TemplateResponse = fake_template_response

        response = main.night_mode_preview(
            request=SimpleNamespace(),
            max_tasks=2,
            stop_on_consecutive_errors=3,
        )
    finally:
        main.list_tasks = original_list_tasks
        main.base_context = original_base_context
        main.templates.TemplateResponse = original_template_response

    report = captured["night_mode_report"]
    assert_true("route_template_index", response.template_name == "index.html")
    assert_true("route_selected_count", report["selected_count"] == 2)
    assert_true("route_stop_on_consecutive_errors", report["stop_on_consecutive_errors"] == 3)
    assert_true("route_creates_no_tasks", "last_queue_add" not in captured)
    assert_true("route_new_paid_submit_started_false", report["new_paid_submit_started"] is False)


def check_limits() -> None:
    assert_true("parse_limited_int_caps_high", main.parse_limited_int(500, default=5, minimum=1, maximum=50) == 50)
    assert_true("parse_limited_int_caps_low", main.parse_limited_int(0, default=5, minimum=1, maximum=50) == 1)
    assert_true("parse_limited_int_default", main.parse_limited_int("bad", default=5, minimum=1, maximum=50) == 5)


def main_check() -> None:
    print("=== Stage 10 Night Mode dry-run check ===")
    check_helper_plan()
    check_route_preview()
    check_limits()
    print("RESULT=STAGE10_NIGHT_MODE_DRY_RUN_OK")


if __name__ == "__main__":
    main_check()
