# Seedance

Local Windows GUI for Segmind Seedance 2.0 video generation.

Current focus: product-facing local workspace with projects, single generation history, queue, CSV import and safe paid-action confirmations.

Canonical project code path:
C:\Users\zerot\Desktop\Codex\Программист\seedance_gui_windows

Windows output root:
C:\AI_OUTPUT

Desktop launcher:
C:\Users\zerot\Desktop\Seedance GUI.lnk

The old WSL copy is no longer the active workspace. Use this Windows copy for development, verification and launches unless migration from WSL is explicitly requested.

Security:
The Segmind API key is stored only in .env.
Do not send .env to chat, GitHub, screenshots, or archives.

## Output storage model

The active project is selected in the GUI and stored locally in:

    data/active_project.json

C:\AI_OUTPUT is the common Windows output root. The active project is a sibling folder under that root, for example:

    C:\AI_OUTPUT\Another_project\

The GUI installation stays the same. Only the active project folder changes.

## Stage 7 output structure

The active project is selected in the GUI and stored locally in data/active_project.json.

Output root:

    C:\AI_OUTPUT

Example active project:

    C:\AI_OUTPUT\Psailor_kun

Current result structure:

    C:\AI_OUTPUT\Psailor_kun\videos\
      Episode_01_Scene_001_take_000001.mp4
      Episode_01_Scene_001_take_000002.mp4
      Episode_01_Scene_002_take_000001.mp4

    C:\AI_OUTPUT\Psailor_kun\last_frames\
      Episode_01_Scene_001_take_000001_last_frame.png
      Episode_01_Scene_001_take_000002_last_frame.png

    C:\AI_OUTPUT\Psailor_kun\runs\
      Episode_01_Scene_001_take_000001\
        output.mp4
        prompt.txt
        params.json
        refs.json
        status.json
        summary.json
        errors.log

Rules:

- videos/ is the main folder for final MP4 files.
- last_frames/ is the main folder for final-frame PNG files with take-based names.
- runs/ is the technical archive for each generation.
- runs/<take>/last_frame.png is still kept for continuation chains and debugging.
- The final filename includes episode, scene and take number.
- Take numbers are counted separately per Episode + Scene.
- Queued tasks keep the project that was active at Add to Queue time.
- If the active project is switched before Start Queue, the queued task still saves into its original project.
- The old nested structure results/Episode/Scene/take is no longer used for new results.

## Stage 8 continuation workflow

Corrected project decision:

- `return_last_frame=true` returns the previous clip final frame at `video.last_frame_url`.
- The worker saves it as `runs/<take_stem>/last_frame.png`.
- Main Stage 8 workflow is automatic queue chaining.
- A child continuation task must use the parent saved image as one of the next task's `reference_images`.
- Manual `Continue from previous take` remains secondary/debug fallback only.
- It should not default to `first_frame_url`.
- The worker should upload the local `last_frame.png` through `upload_asset`, then append the returned URL to `reference_images`.
- Other reference images may still be used.
- `first_frame_url` is only a future optional alternative mode, not the current project workflow.
- For cheap continuation tests, prefer `seedance-2.0-fast`.
- Backend queue chaining is validated.
- Real paid continuation test passed for child task #26 from parent task #25.
- Chain Builder route: `POST /add-continuation-chain`.
- Chain Builder creates queued tasks only and does not start paid generation.
- GUI smoke-test passed: `RESULT=STAGE8_CHAIN_BUILDER_GUI_SMOKE_TEST_OK`.
- Test chain was cancelled safely: tasks #27, #28, #29 cancelled; queued_count=0.

See: `docs/CONTINUATION_WORKFLOW.md`.

## Current GUI layout

The GUI is tab-based:

- Projects
- Single Generation
- History
- Queue

Current state:

- Continuation Chain is no longer a main tab; queue/CSV workflows are the primary path for normal users.
- Queue and Single Generation now share the same real generation worker path.
- Worker backend queue chaining is validated.
- DB schema and Segmind API client are unchanged.

Parked items:

- Parallel queues
- Cost limits

## Stage 9 CSV batch import

The Queue tab includes Batch CSV Import.

Route:

    POST /batch-import

CSV header:

    episode_name,scene_name,prompt,model,duration,resolution,aspect_ratio,seed,generate_audio,reference_paths

Behavior:

- Preview mode validates the CSV and creates no tasks.
- Confirm mode validates the CSV again and creates queued tasks only when there are zero errors.
- One CSV row creates one queued task.
- reference_paths are split by semicolon and must point to existing image files.
- Import creates queued tasks only and does not start paid generation.
- Imported tasks use return_last_frame=True.
- first_frame_url is not used by the import path.

Dry-run passed:

    RESULT=STAGE9_BATCH_IMPORT_DRY_RUN_OK

Manual Stage 9 GUI smoke-tests passed after Stage 11 UI polish:

    RESULT=STAGE9_CSV_PREVIEW_SMOKE_TEST_DONE
    RESULT=STAGE9_CSV_CONFIRM_AND_CANCEL_SMOKE_TEST_DONE

Smoke-test notes:

- Preview showed 2 valid rows and created zero queued tasks.
- Confirm created queued tasks #30 and #31.
- Test tasks #30 and #31 were immediately cancelled.
- Queue safety after cancel: queued_after_cancel=0.
- Paid generation did not start.

## Stage 10 night mode safety controls

The Queue tab includes Night Mode Safety Preview.

Route:

    POST /night-mode-preview

Behavior:

- Builds a queue run plan only.
- Does not start the queue.
- Does not call Segmind.
- Does not create, update or delete queued tasks.
- Shows queued count, selected count, dependent continuation task count and parent-blocked count.
- Includes max_tasks and stop_on_consecutive_errors controls.
- Keeps dependent continuation chains sequential.

Dry-run passed:

    RESULT=STAGE10_NIGHT_MODE_DRY_RUN_OK

## Stage 11 startup and diagnostics

Start the GUI through the desktop shortcut:

    C:\Users\zerot\Desktop\Seedance GUI.lnk

Or from the project root:

    .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 7860

Default URL:

    http://127.0.0.1:7860

Optional port override:

    .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 7861

The launcher starts Uvicorn only. It does not start queue processing by itself.

Final safe diagnostic command:

    .venv\Scripts\python.exe -u scripts\check_stage11_final_diagnostics.py
    .venv\Scripts\python.exe -u scripts\check_cost_estimates.py
    .venv\Scripts\python.exe -u scripts\check_queue_history_cards.py

The diagnostic command runs compile checks and safe dry-run checks. It does not start paid generation.

Final diagnostics passed:

    RESULT=STAGE11_FINAL_DIAGNOSTICS_OK

## Product UI polish

The Stage 11 baseline includes a small UI polish pass:

- Header is product-facing and no longer shows internal stage/version text.
- Queue tab keeps Add to Queue, Queue Controls and Queue / History visible; CSV import and Night Mode preview are advanced sections.
- Paid queue actions are visually separated and labeled with `paid`
- CSV and Night Mode preview actions are labeled as safe previews
- Completed/cancelled task history is collapsed in the UI only; tasks are not deleted or changed
- Top bar balance shows Segmind credits from the read-only API-key endpoint `https://api.segmind.com/v1/get-user-credits`
- Queue history uses History-style cards; queued/unsubmitted items can be edited in place or removed from the queue
- Queue controls show progress and estimated total cost; Start Full Queue runs the paid queue loop in the background while the page auto-refreshes
- Batch CSV Import supports optional `continuation_group,continuation_index` columns; rows in the same group are linked so each next task waits for the previous task and uses its `last_frame.png` as a reference image
- History explains the pre-submit processing stage while reference images are uploading before a Segmind request id exists
- Drag/drop JavaScript is covered by `scripts/check_dragdrop_js_regression.py`

Safe UI polish check:

    .venv\Scripts\python.exe -u scripts\check_stage11_ui_polish.py

Stable backup after UI polish and Stage 9 smoke-tests:

    /home/iokramer/seedance_gui_backups/stable_stage11_ui_polished_and_smoke_tested_20260621_093904


## Current handoff — 2026-06-24

Today the product UI cleanup moved beyond the old Stage 11 wording.

Implemented and verified:

- Git is initialized; `.gitignore` excludes `.env`, virtualenv, sqlite DB, logs, snapshots, tmp files and active project state.
- Header no longer shows internal stage/version text.
- Main tabs are: Projects, Single Generation, History, Queue.
- Projects screen includes editable API settings and inactive project deletion.
- Single Generation starts in the background and immediately appears in History as processing.
- Single Generation now dispatches through the same proven queue worker path by concrete `task_id`.
- Single Generation and Queue both accept drag/drop reference files.
- Queue reference input now accepts image, video and audio files via `reference_files`.
- Image references are sent to Segmind. Video/audio references are saved with the task/history but are not sent to the API client yet.
- Attached references are visible in Queue before submit and in queue rows after task creation.
- Prompt reference tokens are normalized to `<@filename>`.
- EN/RU language switch exists for main UI labels.
- Per-generation cost display is implemented. It prefers actual cost fields from Segmind response payloads and otherwise falls back to official Seedance pricing estimates.
- Account balance is read from the read-only API-key endpoint `https://api.segmind.com/v1/get-user-credits`.
- Top bar shows the current balance under the EN/RU switch, with RU translation.
- Queue history now uses the same card layout as Single Generation history: video preview, refs, settings, status, cost, folder link, Edit prompt and Regenerate.
- Queue cards edit/regenerate into Single Generation, so only the selected queue item is regenerated.
- Queue UI uses stable human labels `Queue #N` and item labels `N-M`; technical DB ids stay in Debug / files.

Safe verification passed:

    .venv\Scripts\python.exe -m compileall app\main.py app\queue_worker.py
    .venv\Scripts\python.exe -u scripts\check_stage11_ui_polish.py
    .venv\Scripts\python.exe -u scripts\check_stage11_final_diagnostics.py

Safe route checks performed without paid/API calls:

- Queue route saved image/audio/video refs and normalized prompt to `<@...>`.
- Single Generation route called the concrete-task worker and normalized prompt to `<@...>`.

Open next task:

- If Segmind later exposes actual `cost` in result/status payloads, the UI will prefer it automatically.
- Account balance remains open until an official/stable API-key endpoint is found or the user explicitly approves a dashboard/private endpoint approach.


## Backup rules

Safe backups must exclude:

- .env
- .venv/
- __pycache__/
- *.pyc
- .pytest_cache/
- runtime sqlite DB files
- outputs/
- generated videos and heavy media/results

Stable backups:

- Stage 8: /home/iokramer/seedance_gui_backups/stable_stage8_complete_20260620_235818
- Stage 9: /home/iokramer/seedance_gui_backups/stable_stage9_complete_20260621_001912
- Stage 10: /home/iokramer/seedance_gui_backups/stable_stage10_complete_20260621_003156
- Stage 11: /home/iokramer/seedance_gui_backups/stable_stage11_complete_20260621_003956
