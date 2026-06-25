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


def get_task(task_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM generation_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    if row is None:
        return None

    data = dict(row)
    data["params"] = json.loads(data.pop("params_json"))
    data["refs"] = json.loads(data.pop("refs_json"))
    return data


def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as conn:
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
        data = dict(row)
        data["params"] = json.loads(data.pop("params_json"))
        data["refs"] = json.loads(data.pop("refs_json"))
        result.append(data)

    return result


def get_next_queued_task() -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM generation_tasks
            WHERE status = 'queued'
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        return None

    data = dict(row)
    data["params"] = json.loads(data.pop("params_json"))
    data["refs"] = json.loads(data.pop("refs_json"))
    return data


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
