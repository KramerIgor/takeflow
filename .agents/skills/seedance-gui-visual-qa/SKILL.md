---
name: seedance-gui-visual-qa
description: Visually verify Seedance GUI changes at http://127.0.0.1:7860 with browser inspection, screenshots, responsive checks, and safe interaction boundaries. Use for Single Generation UX, History tab, drag-and-drop references, chips/cards, and visual regressions.
---

# Seedance GUI Visual QA

Use browser verification for UI changes. Do not trigger paid generation.

## Workflow

1. Start or confirm the GUI server with `scripts/start_gui.sh` if needed.
2. Open `http://127.0.0.1:7860`.
3. Verify the changed tab or workflow only.
4. Check desktop and narrow viewport layout.
5. Inspect console/network errors when possible.
6. For paid actions, stop at the confirmation/warning state. Do not confirm.
7. Report visual evidence and remaining issues in Russian.

## Seedance UI Rules

- GUI text stays English.
- Technical identifiers stay English.
- Single Generation polish is the active UX scope.
- Queue, Batch CSV Import, Queue Controls, Night Mode, and Continuation Chain are regression-sensitive; do not change them unless the task requires it.
- `Regenerate` must warn: `This will start a paid generation. Continue?`

Read `references/seedance-visual-checklist.md` before final visual verification.
