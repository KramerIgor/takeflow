---
name: seedance-gui-paid-safety
description: Enforce Seedance GUI safety boundaries for .env, Segmind API key, paid generation, result folders, tasks, DB schema, Segmind API client, queue loops, and regenerate actions. Use before any Seedance task that might touch secrets, paid API calls, outputs, queue execution, or storage.
---

# Seedance GUI Paid Safety

This project can spend money and contains a real API key. Default to safe dry-runs and UI-only verification.

## Hard Rules

- Do not read, print, log, copy, screenshot, archive, or summarize `.env`.
- Do not output the Segmind API key in chat, terminal, logs, diffs, or archives.
- Do not run paid generation without separate explicit user confirmation.
- Do not click or confirm `Regenerate` during setup or QA unless explicitly authorized.
- Do not delete tasks, results, videos, runs, runtime DB files, or output folders.
- Do not change DB schema without explicit confirmation.
- Do not change the Segmind API client unless a concrete bug requires it.
- Do not start queue paid loops, Night Mode runs, or continuation paid runs without confirmation.

## Required Warning

Any `Regenerate` action must show:

`This will start a paid generation. Continue?`

## Safe Alternatives

- Use preview/dry-run commands.
- Verify UI state before the final paid action.
- Inspect code paths without reading secrets.
- Use existing diagnostics that state they do not start paid generation.

Read `references/paid-safety-checklist.md` for confirmation points.
