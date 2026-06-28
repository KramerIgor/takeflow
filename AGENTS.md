# AGENTS.md — Seedance GUI project instructions

## Project role

This repository is a local WSL/Ubuntu GUI for generating anime videos through Segmind Seedance 2.0 / Seedance 2.0 Fast.

The project is not a generic API playground. The main goal is a practical local GUI with queue, project folders, episode/scene/take naming, continuation by last frame, batch import and night mode.

## Current status

Completed stages: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11.

Current stage: product UI cleanup baseline after Stage 11.

Active project is local runtime state in `data/active_project.json`; do not hardcode it in implementation.

Project code path in WSL:

    ~/seedance_gui

Output root:

    /mnt/c/AI_OUTPUT

GUI URL:

    http://127.0.0.1:7860

Final Stage 7 backup:

    /home/iokramer/seedance_gui_backups/stable_stage7_complete_20260620_201725

Stable Stage 8 tab UI backup:

    /home/iokramer/seedance_gui_backups/stable_stage8_tabs_ui_20260620_223731

Backup before Stage 8 backend chaining:

    /home/iokramer/seedance_gui_backups/pre_stage8_backend_chaining_20260620_225337

Stable Stage 8 complete backup:

    /home/iokramer/seedance_gui_backups/stable_stage8_complete_20260620_235818

Pre Stage 9 CSV import backup:

    /home/iokramer/seedance_gui_backups/pre_stage9_csv_import_20260621_000628

Stable Stage 9 complete backup:

    /home/iokramer/seedance_gui_backups/stable_stage9_complete_20260621_001912

Pre Stage 10 night mode controls backup:

    /home/iokramer/seedance_gui_backups/pre_stage10_night_mode_controls_20260621_002107

Stable Stage 10 complete backup:

    /home/iokramer/seedance_gui_backups/stable_stage10_complete_20260621_003156

Pre Stage 11 packaging backup:

    /home/iokramer/seedance_gui_backups/pre_stage11_packaging_20260621_003507

Stable Stage 11 complete backup:

    /home/iokramer/seedance_gui_backups/stable_stage11_complete_20260621_003956


## Latest handoff — 2026-06-24

Current UI state:

- Main tabs: Projects, Single Generation, History, Queue.
- Continuation Chain is not a primary tab.
- Single Generation starts in background, appears in History, and uses the shared concrete-task queue worker path.
- Single Generation and Queue both accept image/video/audio reference files through drag/drop or file picker.
- Queue uses `reference_files`, not `reference_images`, for UI uploads.
- Images are sent to the current Segmind API client; video/audio refs are stored with the task/history and shown in UI, but not sent to API yet.
- Prompt reference tokens should be saved as `<@filename>`.
- Main UI labels have EN/RU switching.

Current verification:

    RESULT=STAGE11_UI_POLISH_OK
    RESULT=STAGE11_FINAL_DIAGNOSTICS_OK

Current product behavior:

- Per-generation cost display is implemented: prefer actual Segmind response cost fields, otherwise use official Seedance pricing estimates.
- Top bar balance reads Segmind credits through the read-only API-key endpoint `https://api.segmind.com/v1/get-user-credits`; do not print the API key or raw `.env`.
- Dashboard billing endpoints under `cloud-api.segmind.com` require JWT cookies and are not needed for the local balance display.
- Queue history uses card layout matching Single Generation history.
- Queue `Edit prompt` and `Regenerate` route users into Single Generation for one selected item.
- Queue `Edit in queue` updates one still-queued item in place without changing its queue position.
- Queue `Remove from queue` is available only for still-queued/unsubmitted items and does not delete generated files.
- Queue numbering is human-readable: `Queue #N` groups and `N-M` item labels; technical task ids stay in debug details.
- While reference images are uploading, a Single Generation can be `processing` before Segmind has a request id; History shows this pre-submit stage explicitly.
- Reference image upload uses longer write/read timeouts and retries to reduce `WriteTimeout` failures before submit.
- `scripts/check_dragdrop_js_regression.py` guards against queue-edit JavaScript leaking into Single Generation drag/drop code.
- CSV batch import supports optional `continuation_group` and `continuation_index`; rows in the same group become dependent queue tasks using `last_frame_as_reference`.
- Queue loop supports up to 50 tasks per paid run, enough for longer chained shot lists.
- History, Queue, cleanup/recovery, Night Mode preview, and Start Queue Loop are scoped to the active project.
- Queue controls expose progress and estimated total queue cost; Start Full Queue launches the paid queue loop in a background thread and Start Next Item is the single-step action.


## Current storage structure

New results must use the flat Stage 7 structure.

Final user MP4 files:

    Project/videos/Episode_01_Scene_001_take_000001.mp4

Technical run archive:

    Project/runs/Episode_01_Scene_001_take_000001/
      output.mp4
      prompt.txt
      params.json
      refs.json
      status.json
      summary.json
      errors.log
      last_frame.png

Do not create new nested results/Episode/Scene/take folders.

## API facts already confirmed

Seedance submit, polling, result fetch and asset upload are already implemented.

Do not reimplement the API client unless a concrete bug is found.

A real paid Stage 8 test confirmed:

    return_last_frame=true

returns last frame at:

    video.last_frame_url

The worker saved it as:

    Project/runs/<take_stem>/last_frame.png

The paid test request id was:

    1d22c000af50a8597ad64748bb87287c

Stage 8 backend queue chaining dry-run passed:

    RESULT=STAGE8_BACKEND_CHAINING_DRY_RUN_OK

Real paid continuation test passed:

    Parent task id: 25
    Child continuation task id: 26
    Child status: completed
    Child output: /mnt/c/AI_OUTPUT/Psailor_kun/videos/Episode_00_Scene_998_LastFrame_API_Test_take_000002.mp4
    Child run dir: /mnt/c/AI_OUTPUT/Psailor_kun/runs/Episode_00_Scene_998_LastFrame_API_Test_take_000002
    Child last frame: /mnt/c/AI_OUTPUT/Psailor_kun/runs/Episode_00_Scene_998_LastFrame_API_Test_take_000002/last_frame.png

Confirmed backend behavior: parent last_frame.png is uploaded through existing upload_asset and appended to child reference_images. first_frame_url is not the default workflow.

Stage 8 Chain Builder route still exists as a backend/queue capability, but Continuation Chain is not a primary tab in the current product UI.

Chain Builder route:

    POST /add-continuation-chain

Chain Builder creates queued tasks only. It does not start paid generation.

Stage 8 Chain Builder GUI smoke-test passed:

    RESULT=STAGE8_CHAIN_BUILDER_GUI_SMOKE_TEST_OK

Test chain was cancelled safely:

    tasks #27, #28, #29 cancelled
    queued_count=0

For API contract tests, prefer:

    seedance-2.0-fast

For final quality renders, use:

    seedance-2.0

Continuation should use the saved last_frame.png as one of the next task reference_images. It is not the default first_frame_url workflow.

Important: The default continuation mode for this project is last_frame_as_reference: upload last_frame.png and add it to reference_images.

## Stage 8 direction

Do not keep working only from console.

Current GUI state:

- GUI is FastAPI + Uvicorn + Jinja2 templates + static CSS.
- GUI is now tab-based:
  - Projects
  - Single Generation
  - History
  - Queue
- Continuation Chain is not a primary tab in the current product UI.
- Worker backend queue chaining is validated.
- Single Generation now dispatches through the same concrete-task worker path as Queue.
- DB schema and Segmind API client are unchanged.
- Continuation Chain is no longer a primary tab; continuation remains available through queue/task flows.

Completed product-facing GUI integration:

1. Show whether a completed task has last_frame.png.
2. Show/open last_frame.png from GUI.
3. Keep Continue from previous take as a secondary/debug fallback in Queue row Debug / files.

Current Stage 8 result:

1. Stage 8 backend chaining is validated.
2. Chain Builder UI is implemented.
3. Stage 8 is complete as working baseline.

ffmpeg is installed but fallback only. Main last-frame path is API response video.last_frame_url.

Parked items:

- Parallel queues.
- Cost limits.

## Stage 9 batch import

Stage 9 CSV batch import is implemented as a working baseline.

Batch import route:

    POST /batch-import

CSV header:

    episode_name,scene_name,prompt,model,duration,resolution,aspect_ratio,seed,generate_audio,reference_paths

Behavior:

- Batch CSV Import is in the Queue tab.
- Preview mode validates the CSV and creates no tasks.
- Confirm mode validates the CSV again and creates queued tasks only when there are zero errors.
- One CSV row creates one queued task.
- reference_paths are split by semicolon and must point to existing image files.
- Imported tasks use return_last_frame=True.
- Imported task params include batch_import_id and batch_row_number.
- first_frame_url is not used by the import path.
- Batch import does not start paid generation.

Stage 9 dry-run passed:

    RESULT=STAGE9_BATCH_IMPORT_DRY_RUN_OK

Stage 8 regression checks still pass:

    RESULT=STAGE8_BACKEND_CHAINING_DRY_RUN_OK
    RESULT=STAGE8_TABBED_UI_OK

## Stage 10 night mode safety controls

Stage 10 Night Mode Safety Preview is implemented as a working baseline.

Night mode preview route:

    POST /night-mode-preview

Behavior:

- Night Mode Safety Preview is in the Queue tab.
- It builds a queue run plan only.
- It does not start the queue.
- It does not call Segmind.
- It does not create, update or delete queued tasks.
- Controls include max_tasks and stop_on_consecutive_errors.
- Report includes queued count, selected count, dependent continuation task count and parent-blocked count.
- Dependent continuation chains stay sequential.
- Existing paid queue buttons still require explicit user confirmation.

Stage 10 dry-run passed:

    RESULT=STAGE10_NIGHT_MODE_DRY_RUN_OK

## Stage 11 startup and diagnostics

Stage 11 packaging, startup instructions and final diagnostics are implemented as a working baseline.

Startup script:

    scripts/start_gui.sh

Default GUI URL:

    http://127.0.0.1:7860

Final safe diagnostic command:

    .venv/bin/python -u scripts/check_stage11_final_diagnostics.py

The startup script launches Uvicorn only. It does not start queue processing by itself.

The final diagnostic command runs compile checks and safe dry-run checks. It does not start paid generation.

Final diagnostic result:

    RESULT=STAGE11_FINAL_DIAGNOSTICS_OK

## Cost rule

Any real Segmind generation is paid.

Before paid generation, explicitly state:

    paid_generation=True

and explain the exact purpose.

Batch, night mode and continuation chains require explicit user confirmation.

## Copyable command rule for ChatGPT

When giving WSL terminal commands to the user, use one bash block only.

Markers must be inside the code block as bash comments:

    # 🟢 BEGIN_COPY
    commands
    # 🟢 END_COPY

If relevant output is needed, the command should print green output markers:

    printf '\033[32m🟢 BEGIN_COPY\033[0m\n'
    checks
    printf '\033[32m🟢 END_COPY\033[0m\n'

Do not put markdown triple-backticks inside bash heredocs. This previously broke copy/paste.

Use set +e, not set -e.

## When to use Codex

Use Codex or an IDE coding agent for broad multi-file edits.

Use chat for:
- plan control;
- architecture decisions;
- cost decisions;
- reviewing diagnostics;
- approving stage transitions;
- writing small safe commands.

Before Codex makes broad changes, create a safe snapshot.

## Codex working rules

- User-facing GUI text stays in English unless the user explicitly asks to localize it.
- Reports, explanations, questions and summaries to the user should be in Russian.
- Technical identifiers stay in English:
  - file names
  - function names
  - class names
  - endpoints
  - database fields
  - API payload fields
  - exact status values
  - CLI commands
- Before every edit-step, follow the current project stage and do not expand scope.
- If a task belongs to a later stage, park it instead of implementing it.
- For scoped edit-steps, Codex may create a safe backup automatically when needed.
- Codex may create Git commits when it is useful to preserve a completed working checkpoint. Before committing, verify `git status`, keep secrets/runtime outputs out of the commit, and use a concise descriptive commit message.
- For long operations and paid-generation steps, commands or reports should include visible progress/status updates so the user does not think the process is stuck.
- For related verification checks, bundle them into one consolidated check step instead of many small copy-paste checks.
- Ask for explicit confirmation only for:
  - paid generation
  - .env/secrets
  - destructive actions
  - DB schema/storage changes
  - API client rewrite
  - broad scope expansion
  - stage transitions

## Stage 8 correction: last frame as reference image

The user corrected the continuation workflow.

Do NOT use previous last_frame as first_frame_url by default.

Correct workflow:

    previous runs/<take>/last_frame.png
    -> upload_asset
    -> append returned URL to reference_images of the next task

The next clip should be guided by the previous final frame as a reference, not forced to start from it exactly.

first_frame_url is parked as a possible future optional mode only.

## Product UI cleanup scope

Current UI cleanup scope:

- Drag-and-drop reference files are available on Single Generation and Queue forms.
- Accept image, video, and audio reference files in GUI/storage/history.
- Show attached references as chips/cards with image thumbnail or media badge, filename, and remove button.
- Replace Episode/Scene in Single Generation with one optional `Name` field. If empty, backend should generate a safe name such as `generation00001-22062026`.
- A separate `History` tab shows one-off Single Generation tasks/runs only, not queue/batch/continuation tasks.
- In History, show video preview/player, name, prompt, attached references, model, duration, resolution, aspect ratio, seed, output filename/path, times if available, and status/error if failed.
- Add `Edit prompt` and `Regenerate`.
- `Regenerate` must show exactly: `This will start a paid generation. Continue?`
- Add `@reference` prompt tokens for attached references and preserve those tokens in saved prompts.
- If video/audio references are not supported by the Segmind API client, store them in GUI/storage/history and show `Stored in history; not sent to API yet`; leave video/audio API submission parked.

Additional Codex local skills live in `.agents/skills`:

- `seedance-gui-workflow`
- `seedance-gui-visual-qa`
- `seedance-gui-paid-safety`
- `seedance-gui-context-compact`

These skills are project-local. Do not copy their Seedance-specific paths, paid-generation rules, or roadmap into universal programmer skills.

