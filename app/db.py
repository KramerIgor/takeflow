from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import sqlite3
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "seedance_gui.sqlite3"

ALLOWED_STATUSES = {
    "queued",
    "processing",
    "completed",
    "failed",
    "recoverable",
    "paused",
    "cancelled",
}


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generation_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                status TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt TEXT NOT NULL,

                params_json TEXT NOT NULL,
                refs_json TEXT NOT NULL,

                request_id TEXT,
                output_path TEXT,
                run_dir TEXT,
                error TEXT,

                started_at TEXT,
                completed_at TEXT,
                elapsed_total_seconds INTEGER,
                inference_time REAL
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generation_tasks_status_id
            ON generation_tasks(status, id)
            """
        )

        conn.commit()


def create_task(
    *,
    model: str,
    prompt: str,
    params: dict[str, Any],
    refs: list[dict[str, Any]] | None = None,
    status: str = "queued",
) -> int:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid task status: {status}")

    now = utc_now()

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO generation_tasks (
                created_at,
                updated_at,
                status,
                model,
                prompt,
                params_json,
                refs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                now,
                status,
                model,
                prompt,
                json.dumps(params, ensure_ascii=False),
                json.dumps(refs or [], ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def _decode_task_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["params"] = json.loads(data.pop("params_json"))
    data["refs"] = json.loads(data.pop("refs_json"))
    return data


def _same_path(left: str | Path, right: str | Path) -> bool:
    try:
        return Path(left).resolve() == Path(right).resolve()
    except Exception:
        return str(left) == str(right)


def _path_inside(path_value: str | None, base_value: str | Path | None) -> bool:
    if not path_value or not base_value:
        return False

    try:
        return Path(path_value).resolve().is_relative_to(Path(base_value).resolve())
    except Exception:
        return False


def task_matches_project(
    task: dict[str, Any],
    *,
    project_name: str | None = None,
    project_dir: str | Path | None = None,
) -> bool:
    project_name = str(project_name or "").strip()
    project_dir_text = str(project_dir or "").strip()

    if not project_name and not project_dir_text:
        return True

    params = task.get("params") if isinstance(task.get("params"), dict) else {}
    task_project_name = str(params.get("project_name") or params.get("active_project_name") or "").strip()
    task_project_dir = str(params.get("project_dir") or params.get("active_project_dir") or "").strip()

    if project_name and task_project_name:
        return task_project_name == project_name

    if project_dir_text and task_project_dir:
        return _same_path(task_project_dir, project_dir_text)

    if task_project_name or task_project_dir:
        return False

    if project_dir_text:
        for path_value in (task.get("run_dir"), task.get("output_path")):
            if _path_inside(path_value, project_dir_text):
                return True

    return False


def get_task(task_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM generation_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    if row is None:
        return None

    return _decode_task_row(row)


def list_tasks(
    limit: int = 50,
    *,
    project_name: str | None = None,
    project_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    filtered = bool(project_name or project_dir)

    with get_connection() as conn:
        if filtered:
            rows = conn.execute(
                """
                SELECT *
                FROM generation_tasks
                ORDER BY id DESC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT *
                FROM generation_tasks
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    result = []
    for row in rows:
        data = _decode_task_row(row)
        if filtered and not task_matches_project(data, project_name=project_name, project_dir=project_dir):
            continue
        result.append(data)
        if len(result) >= limit:
            break

    return result


def get_next_queued_task(
    *,
    project_name: str | None = None,
    project_dir: str | Path | None = None,
) -> dict[str, Any] | None:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM generation_tasks
            WHERE status = 'queued'
            ORDER BY id ASC
            """
        ).fetchall()

    for row in rows:
        data = _decode_task_row(row)
        if task_matches_project(data, project_name=project_name, project_dir=project_dir):
            return data

    return None


def update_task_status(task_id: int, status: str, error: str | None = None) -> None:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid task status: {status}")

    now = utc_now()

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE generation_tasks
            SET status = ?,
                error = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (status, error, now, task_id),
        )
        conn.commit()


def delete_task(task_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM generation_tasks WHERE id = ?", (task_id,))
        conn.commit()


def update_task_fields(task_id: int, **fields: Any) -> None:
    if not fields:
        return

    allowed_fields = {
        "status",
        "request_id",
        "output_path",
        "run_dir",
        "error",
        "started_at",
        "completed_at",
        "elapsed_total_seconds",
        "inference_time",
    }

    unknown = set(fields) - allowed_fields
    if unknown:
        raise ValueError(f"Unknown task fields: {sorted(unknown)}")

    if "status" in fields and fields["status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid task status: {fields['status']}")

    fields["updated_at"] = utc_now()

    assignments = ", ".join(f"{name} = ?" for name in fields)
    values = list(fields.values())
    values.append(task_id)

    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE generation_tasks
            SET {assignments}
            WHERE id = ?
            """,
            values,
        )
        conn.commit()


def update_task_payload(
    task_id: int,
    *,
    model: str,
    prompt: str,
    params: dict[str, Any],
    refs: list[dict[str, Any]] | None = None,
) -> None:
    now = utc_now()

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE generation_tasks
            SET model = ?,
                prompt = ?,
                params_json = ?,
                refs_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                model,
                prompt,
                json.dumps(params, ensure_ascii=False),
                json.dumps(refs or [], ensure_ascii=False),
                now,
                task_id,
            ),
        )
        conn.commit()
