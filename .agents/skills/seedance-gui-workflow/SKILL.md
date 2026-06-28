---
name: seedance-gui-workflow
description: Work on the Seedance GUI project-local workflow in /home/iokramer/seedance_gui, especially Stage 11/post-MVP Single Generation UX polish, FastAPI/Uvicorn/Jinja2/static CSS changes, safe backups, and local verification. Use for Seedance GUI implementation, debugging, or planning tasks.
---

# Seedance GUI Workflow

Use this skill only inside `/home/iokramer/seedance_gui`.

## Required Context

Before editing, read project-local instructions and current state:

- `AGENTS.md`
- `README.md`
- `docs/PROJECT_STATE.md`
- `docs/CONTINUATION_WORKFLOW.md` when continuation, queue, or last-frame behavior is mentioned

Do not read `.env`.

## Current Scope

Default current work is post-Stage-11 product UI cleanup and cost/balance follow-up:

- Keep Projects, Single Generation, History and Queue as the primary tabs.
- Single Generation and Queue both support drag/drop reference files.
- Queue uses `reference_files` for image/video/audio uploads.
- Prompt reference tokens should be stored as `<@filename>`.
- Single Generation uses the shared concrete-task queue worker path.
- Per-generation cost display exists; prefer actual Segmind response cost fields, otherwise use official pricing estimates.
- Top bar balance reads Segmind credits through the read-only API-key endpoint `https://api.segmind.com/v1/get-user-credits`.
- Queue history uses Single Generation-style cards; edit/regenerate should target one selected item through Single Generation.
- Queue labels should remain human-readable: `Queue #N` and `N-M`; DB ids belong in debug details.
- CSV continuation uses optional `continuation_group,continuation_index` and must create queued tasks only; no paid generation starts during import.
- Keep paid actions explicit and confirmed.

## Rules

- Reply to the user in Russian.
- Keep GUI labels, buttons, tabs, statuses, and technical identifiers in English.
- Do not judge prompt artistry when the task is GUI work.
- Do not touch Batch CSV Import, Queue Controls, Night Mode, or continuation internals unless required.
- Do not change DB schema, Segmind API client, or storage contracts without explicit need and confirmation.
- Make a safe backup before broad UI/backend changes.
- One logical edit step should end with one consolidated verification pass.

Read `references/seedance-workflow.md` for file map and checks.
