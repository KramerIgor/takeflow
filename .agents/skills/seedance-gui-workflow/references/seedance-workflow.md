# Seedance Workflow Reference

## Paths

- WSL project: `/home/iokramer/seedance_gui`
- GUI URL: `http://127.0.0.1:7860`
- Windows output root: `C:\AI_OUTPUT`
- WSL output root: `/mnt/c/AI_OUTPUT`
- Active result project: `/mnt/c/AI_OUTPUT/Psailor_kun`

## Stack

- FastAPI
- Uvicorn
- Jinja2 templates
- Static CSS

## Important Files

- `app/main.py`
- `app/templates/index.html`
- `app/static/style.css`
- `app/db.py`
- `app/storage.py`
- `app/queue_worker.py`
- `app/segmind_client.py`
- `scripts/check_stage11_final_diagnostics.py`
- `scripts/check_stage11_ui_polish.py`

## Safe Checks

- `.venv/bin/python -u scripts/check_stage11_final_diagnostics.py`
- `.venv/bin/python -u scripts/check_stage11_ui_polish.py`
- Relevant compile or targeted dry-run checks.

Do not run paid generation checks unless the user explicitly confirms the exact action.
