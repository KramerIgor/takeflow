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

Default current work is Stage 11/post-MVP Single Generation UX polish:

- Add drag-and-drop reference files to the Single Generation prompt area.
- Show attached references as chips/cards.
- Replace Episode/Scene in Single Generation with optional `Name`.
- Add a separate `History` tab for Single Generation tasks/runs only.
- Add `Edit prompt` and `Regenerate`; `Regenerate` must show `This will start a paid generation. Continue?`.
- Add `@reference` tokens for attached references.
- Store image/video/audio references in GUI/storage/history; send only API-supported types to paid submission.

## Rules

- Reply to the user in Russian.
- Keep GUI labels, buttons, tabs, statuses, and technical identifiers in English.
- Do not judge prompt artistry when the task is GUI work.
- Do not touch Queue, Batch CSV Import, Queue Controls, Night Mode, or Continuation Chain unless required.
- Do not change DB schema, Segmind API client, or storage contracts without explicit need and confirmation.
- Make a safe backup before broad UI/backend changes.
- One logical edit step should end with one consolidated verification pass.

Read `references/seedance-workflow.md` for file map and checks.
