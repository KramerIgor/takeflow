---
name: seedance-gui-context-compact
description: Compact Seedance GUI work into a safe project handoff preserving current stage, active scope, WSL/Windows paths, paid-generation rules, .env safety, changed files, verification evidence, and next steps. Use before context compaction or handing Seedance GUI work to another agent.
---

# Seedance GUI Context Compact

Create a compact handoff that protects project state and paid-generation boundaries.

## Keep

- WSL path: `/home/iokramer/seedance_gui`
- GUI URL: `http://127.0.0.1:7860`
- Output roots: `C:\AI_OUTPUT` and `/mnt/c/AI_OUTPUT`
- Active result project: `/mnt/c/AI_OUTPUT/Psailor_kun`
- Stack: FastAPI + Uvicorn + Jinja2 + static CSS
- Current scope: Stage 11/post-MVP Single Generation UX polish
- Paid generation and `.env` guardrails
- Changed files and verification commands/results

## Drop

- Raw logs after extracting the actual failure.
- Long pasted source snippets that are unchanged.
- Repeated baseline facts already in `AGENTS.md`.
- Artistic prompt critique unless the task is explicitly prompt quality.

## Output

Use:

- `Seedance Goal`
- `Current Scope`
- `Guardrails`
- `Relevant Files`
- `Changed Files`
- `Verification`
- `Next Step`

Read `references/seedance-compact-template.md` for the exact template.
