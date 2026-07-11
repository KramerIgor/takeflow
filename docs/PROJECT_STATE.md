# PROJECT_STATE.md — Takeflow current state

Takeflow — локальная AI-video студия для сцен, дублей и очередей, созданная Игорем Олеговичем Крамером / IOKRAMER.

Created by Игорь Олегович Крамер / IOKRAMER.

Release target:

    Version: 0.1.0beta
    Tag: v0.1.0-beta

Release architecture:

- Packaged Windows builds use PyInstaller onedir plus an Inno Setup per-user installer.
- The installed app starts `Takeflow.exe`, which launches the local Uvicorn server and opens `http://127.0.0.1:7860`.
- Runtime updates are checked through `update.json` and downloaded with visible progress. The app does not use `git pull` for end-user updates.
- `.env`, local databases, logs and generated media are excluded from release artifacts.

Updated after moving the active workspace to Windows.

## Current canonical workspace

Use the Windows copy for all normal development, verification and launches:

    C:\Users\zerot\Desktop\Codex\Программист\seedance_gui_windows

Desktop launcher:

    C:\Users\zerot\Desktop\Seedance GUI.lnk

Output root:

    C:\AI_OUTPUT

The Projects screen now exposes an editable output root. Saving a new root creates that folder if needed and recreates the current active project folder under it. Existing project folders are not moved automatically.

The old WSL copy `/home/iokramer/seedance_gui` is historical only. Do not edit or launch it unless the user explicitly asks for WSL migration or comparison.

## Completed

Stages 0–11 are complete.

Stage 7 result structure is fixed:

    Project/videos/
    Project/last_frames/
    Project/runs/

Current storage rule: new runs do not duplicate media in the run archive. Generated MP4 files are saved directly in `Project/videos/`; returned final-frame PNG files are saved directly in `Project/last_frames/`. Legacy `runs/<take>/output.mp4` and `runs/<take>/last_frame.png` are still readable.

The active project is stored in:

    data/active_project.json

Queued tasks store project_name and project_dir at Add to Queue time.

## Stage 8 current state

Stage 8 is complete as a working baseline.

Done:

- Universal last-frame extractor exists in app/last_frame.py.
- Queue worker can save API-returned last frame.
- Real paid test with return_last_frame=true completed.
- Segmind returned last frame at video.last_frame_url.
- Worker saved last frame as runs/<take>/last_frame.png.
- ffmpeg is installed but should be fallback only.
- GUI now uses a product-facing tab layout:
  - Projects
  - Single Generation
  - History
  - Queue
- The tab-based UI is product-facing and actively used.
- Single Generation now dispatches through the same concrete-task worker path as Queue.
- DB schema and Segmind API client are unchanged.
- Continuation Chain is no longer a primary tab; continuation remains a backend/queue capability.
- Manual Continue from previous take remains available only as a secondary/debug fallback inside Queue row Debug / files.
- Backend queue chaining dry-run passed:
  RESULT=STAGE8_BACKEND_CHAINING_DRY_RUN_OK
- Real paid continuation test passed for task #26.
- Backend behavior confirmed: parent last_frame.png is uploaded through existing upload_asset and appended to child reference_images.
- first_frame_url is not the default workflow.
- Chain Builder route still exists:
  POST /add-continuation-chain
- Continuation Chain is not a primary tab in the current product UI.
- Normal continuation work should be driven through Queue/CSV/task flows.

Confirmed run:

    Task id: 25
    Request id: 1d22c000af50a8597ad64748bb87287c
    Run dir: /mnt/c/AI_OUTPUT/Example_project/runs/Episode_00_Scene_998_LastFrame_API_Test_take_000001
    Final video: /mnt/c/AI_OUTPUT/Example_project/videos/Episode_00_Scene_998_LastFrame_API_Test_take_000001.mp4
    Last frame: /mnt/c/AI_OUTPUT/Example_project/runs/Episode_00_Scene_998_LastFrame_API_Test_take_000001/last_frame.png
    API field: video.last_frame_url

Confirmed continuation run:

    Parent task id: 25
    Child continuation task id: 26
    Child status: completed
    Child output: /mnt/c/AI_OUTPUT/Example_project/videos/Episode_00_Scene_998_LastFrame_API_Test_take_000002.mp4
    Child run dir: /mnt/c/AI_OUTPUT/Example_project/runs/Episode_00_Scene_998_LastFrame_API_Test_take_000002
    Child last frame: /mnt/c/AI_OUTPUT/Example_project/runs/Episode_00_Scene_998_LastFrame_API_Test_take_000002/last_frame.png

Stable Stage 8 tab UI backup:

    /home/iokramer/seedance_gui_backups/stable_stage8_tabs_ui_20260620_223731

Backup before backend chaining:

    /home/iokramer/seedance_gui_backups/pre_stage8_backend_chaining_20260620_225337

Stable Stage 8 complete backup:

    /home/iokramer/seedance_gui_backups/stable_stage8_complete_20260620_235818

## Stage 9 current state

Stage 9 is complete as a working baseline.

Done:

- Batch CSV Import section is implemented in the Queue tab.
- Batch import route:
  POST /batch-import
- CSV import requires a header row with:
  episode_name,scene_name,prompt,model,duration,resolution,aspect_ratio,seed,generate_audio,reference_paths
- Preview mode parses and validates the CSV without creating tasks.
- Confirm mode parses and validates the CSV again, then creates queued tasks only if there are zero errors.
- One CSV row creates one queued task.
- reference_paths are split by semicolon.
- reference_paths must point to existing image files with supported suffixes.
- Batch import creates queued tasks only. It does not start paid generation.
- Optional CSV columns `continuation_group,continuation_index` link rows in the same group into a sequential continuation chain.
- In a CSV continuation group, the first row is independent; each next row receives `continuation_mode=last_frame_as_reference` and `parent_task_id` of the previous row.
- Imported tasks use return_last_frame=True.
- Imported task params include batch_import_id and batch_row_number.
- first_frame_url is not used by the batch import path.
- Excel import and Markdown import are not implemented in Stage 9.

Stage 9 dry-run passed:

    RESULT=STAGE9_BATCH_IMPORT_DRY_RUN_OK

Manual Stage 9 GUI smoke-tests passed after Stage 11 UI polish:

    RESULT=STAGE9_CSV_PREVIEW_SMOKE_TEST_DONE
    RESULT=STAGE9_CSV_CONFIRM_AND_CANCEL_SMOKE_TEST_DONE

Smoke-test result:

- Preview showed 2 valid rows and created zero queued tasks.
- Confirm created queued tasks #30 and #31.
- Test tasks #30 and #31 were immediately cancelled.
- Queue safety after cancel:
  queued_after_cancel=0
- Paid generation did not start.

Stage 8 regression checks still pass:

    RESULT=STAGE8_BACKEND_CHAINING_DRY_RUN_OK
    RESULT=STAGE8_TABBED_UI_OK

Stage 9 pre-edit backup:

    /home/iokramer/seedance_gui_backups/pre_stage9_csv_import_20260621_000628

Stable Stage 9 complete backup:

    /home/iokramer/seedance_gui_backups/stable_stage9_complete_20260621_001912

## Stage 11 current state

Stage 11 is superseded by the product UI cleanup baseline.

Done:

- Practical Windows startup:
  C:\Users\zerot\Desktop\Seedance GUI.lnk
- Default GUI URL remains:
  http://127.0.0.1:7860
- Desktop launcher starts Uvicorn only.
- Desktop launcher does not start queue processing by itself.
- Final safe diagnostics script:
  scripts/check_stage11_final_diagnostics.py
- Final diagnostics run compile checks, frontend module/static checks, Stage 10, Stage 9 and Stage 8 dry-run checks.
- Final diagnostics do not start paid generation.
- README includes startup, diagnostics and backup exclusion instructions.

Stage 11 final diagnostics passed:

    RESULT=STAGE11_FINAL_DIAGNOSTICS_OK
    RESULT=COST_ESTIMATES_OK
    RESULT=QUEUE_HISTORY_CARDS_OK

Stage 11 pre-edit backup:

    /home/iokramer/seedance_gui_backups/pre_stage11_packaging_20260621_003507

Stable Stage 11 complete backup:

    /home/iokramer/seedance_gui_backups/stable_stage11_complete_20260621_003956

## Stage 11 UI polish baseline

Morning UI polish after Stage 11 keeps generation logic unchanged.

Done:

- Header status now presents the current baseline as:
  Takeflow
- Queue tab is simplified for normal use; CSV import is an advanced section.
- Paid queue buttons are visually separated and labeled with paid.
- CSV preview actions are styled as safe preview actions.
- Batch CSV Import includes the required columns, optional continuation_group/continuation_index columns, and semicolon-separated reference_paths hint.
- Queue / History shows active and recent tasks for the active project only, with completed/cancelled history collapsed.
- Queue controls show active-project progress and estimated total cost; full queue runs start in the background and rely on auto-refresh for live status.
- No tasks are deleted and no task statuses are changed by this UI grouping.

Safe UI polish check:

    RESULT=STAGE11_UI_POLISH_OK

Stable backup after Stage 11 UI polish and Stage 9 smoke-tests:

    /home/iokramer/seedance_gui_backups/stable_stage11_ui_polished_and_smoke_tested_20260621_093904


## Product UI cleanup handoff — 2026-06-24

This is the current state to use at the next session start.

Done today:

- Main UI is product-facing with a left sidebar: Projects, Single Generation, Queue.
- Repository hygiene is updated: `.gitignore` excludes local secrets, virtualenvs, sqlite DB files/sidecars, logs, `tmp_test_output/`, generated result/media folders and `node_modules/`; `.env.example` is a secret-free generic template.
- Single Generation and one-off History now share one workspace: the form is central, and History is a compact right rail with local refresh and its own scroll.
- Queue now uses the same workspace shape: controls/forms are central, and Queue / History is a compact right rail with local refresh and its own scroll.
- History cards are collapsed by default and show preview, title, status and primary actions. Prompt, references, settings, cost and debug/files are inside Details.
- Single and Queue history rails have separate client-side pagination.
- There is no separate primary History tab.
- Stage/version label is removed from the header.
- API settings can be edited from Projects without showing the current `.env` secret value.
- Inactive projects can be deleted from the UI after confirmation.
- Single Generation starts in the background and appears in the right History rail while processing.
- Single Generation now uses the same queue worker path as Queue, targeted by concrete `task_id`.
- Queue accepts image, video and audio references through `reference_files`.
- Queue and Single Generation both support drag/drop reference files and prompt-local reference chips/cards.
- Attached references now live inside the prompt editor with media thumbnails/badges, a compact Add tile, a `N/9` reference counter, hover/focus remove controls, a prompt-local `@` dropdown, and inline visual chips for saved `<@filename>` tokens.
- Queue rows show attached references after task creation.
- Prompt tokens are stored as `<@filename>`; backend normalizes bare `@filename` when it matches an attached reference.
- EN/RU switch exists for main UI labels.
- Core Single/Queue form labels, compact history actions, pagination and modal controls are covered by the RU/EN switch.
- Git is initialized and AGENTS.md allows commits for completed checkpoints after `git status` and secret/runtime-output review.

Verification passed:

    RESULT=STAGE11_UI_POLISH_OK
    RESULT=STAGE11_FINAL_DIAGNOSTICS_OK

Safe route checks passed without paid/API calls:

- Queue route: image/audio/video refs persisted and prompt normalized to `<@...>`.
- Single Generation route: concrete-task worker dispatch occurred and prompt normalized to `<@...>`.

Current cost and balance behavior:

- Per-generation cost display is implemented.
- The app prefers actual cost fields from Segmind response payloads when present.
- Top bar balance reads Segmind credits through `https://api.segmind.com/v1/get-user-credits`.
- Reference image upload timeout/retry was increased after real Single Generation failures timed out before Segmind submit.
- Drag/drop regression check is included in Stage 11 final diagnostics.
- Existing saved result/status payloads did not include cost, so the app falls back to official Seedance pricing estimates by model/resolution/aspect/duration.
- Single Generation and Queue forms show a local pre-submit cost estimate from the same pricing tables before any paid action is confirmed.
- User dashboard example `seedance-2.0-fast`, 4s, 480p showed about `$0.2273`; official pricing estimate is `~$0.2248`.
- Account balance is available through the read-only API-key endpoint `https://api.segmind.com/v1/get-user-credits`; dashboard billing endpoints still require JWT cookies and are not used.
- Do not use private dashboard endpoints for balance without explicit user approval.
- Top bar shows balance state under the EN/RU language switch; current value is `Unavailable` because no official balance endpoint is known.
- Queue history cards are implemented and mirror Single Generation history cards.
- Queue item `Edit prompt` fills Single Generation with that one item's prompt/settings/refs.
- Queue item `Regenerate` confirms the paid action and submits only that one item through Single Generation; it does not rerun the whole queue or batch. Queued-like queue cards label that action as `Run as Single (paid)` to avoid implying that the whole queue will run.
- Queue display numbering is derived without schema migration: groups use `queue_group_id`, `batch_import_id`, `continuation_chain_id`, or legacy task fallback. UI labels are `Queue #N` and `N-M`.
- Frontend JS is split out of `app/templates/index.html`; the template should stay focused on Jinja-rendered structure, macros and `window.seedanceConfig`.
- `app/static/app.js` is now a small ES module entrypoint. Focused modules live in `app/static/js/`: auto-refresh, i18n, navigation, history pagination, history rail refresh/path opening, model constraints and live cost estimates, shared prompt reference UI helpers, Single Generation references/edit/regenerate/paid confirmation, Queue references/editing and form preference preservation.
- `scripts/check_frontend_modules.py` verifies the module graph and public frontend hooks. `scripts/check_prompt_reference_cost_ui.py` verifies the prompt-local reference and pre-submit cost UI contract. `scripts/check_frontend_browser_cdp.py` is a repeatable safe browser regression for desktop/mobile, RU/EN, refresh guard, drag/drop, prompt references, model-aware reference limits, live cost estimates, history details/pagination and paid modal warning; it stops before paid confirmation.

Current Segmind model support:

- `seedance-2.0`: `480p`, `720p`, `1080p`, `4k`; duration 4-15 seconds.
- `seedance-2.0-mini`: `480p`, `720p`; duration 4, 5, 6, 8, 10, 12, 15 seconds.
- `seedance-2.0-fast`: legacy GUI option, kept to `480p` and `720p`.
- UI selects and CSV validation are model-aware. `4k` is only valid for `seedance-2.0`.
- Reference limits are model-aware. Current Seedance 2.0 Base, Mini and Fast options allow 9 references; future models can set another `reference_file_limit`. The limit is enforced in the prompt UI, normal form posts and CSV validation.
- Cost estimates include official public pricing for current Seedance 2.0 Base, Mini and Fast options; unknown combinations intentionally do not show an estimate.


## Next step

Current stage result:

    Stage 11 complete as working baseline.

Main Stage 8 workflow direction:

    User prepares a continuation chain in the queue.
    Worker runs tasks sequentially.
    Child task waits for parent completion.
    Worker finds parent runs/<take>/last_frame.png.
    Worker uploads that file with existing upload_asset.
    Worker appends uploaded URL to child reference_images.
    Worker submits the child generation.

Do not redo API connection work.

Do not continue with backend-only console scripts unless needed for diagnostics.

## Known correction

For cheap/fast API contract tests use seedance-2.0-fast.

The previous paid last-frame test used seedance-2.0, which worked but was slower and more expensive than necessary for a contract test.

## Corrected continuation workflow

The user corrected Stage 8 workflow.

The previous video's last_frame.png must be used as one of the next generation reference_images.

Do not use first_frame_url as the default continuation workflow.

Correct flow:

    previous runs/<take>/last_frame.png
    -> upload_asset
    -> append uploaded URL to reference_images
    -> submit next generation

Workflow code name:

    continuation_mode=last_frame_as_reference

first_frame_url is parked as a possible optional future mode only.

## Parked items

- Parallel queues.
- Cost limits.

## macOS productization pass — 2026-07-10

- Release target advanced to `0.1.1beta` / `v0.1.1-beta`.
- Windows runtime paths remain unchanged; no existing history or project data is migrated.
- macOS settings and SQLite history use `~/Library/Application Support/Takeflow`.
- macOS launcher logs use `~/Library/Logs/Takeflow` and default projects use `~/Movies/Takeflow`.
- Finder integration uses `open` / `open -R`; Windows continues to use `explorer.exe`.
- The update manifest supports `windows-x64`, `macos-arm64` and `macos-x64` assets while retaining legacy Windows fields.
- `packaging/pyinstaller_takeflow_macos.spec` creates a background `Takeflow.app` bundle with bundle id `com.iokramer.takeflow`.
- `scripts/build_macos_dmg.sh` creates ad-hoc signed Apple Silicon or Intel DMG files and checksum files.
- `.github/workflows/build-macos.yml` builds and smoke-tests both architectures on real GitHub macOS runners before optional release upload.
- The macOS educational beta is not Developer ID signed or notarized. Users follow Apple's one-time Privacy & Security → Open Anyway flow; global Gatekeeper bypass instructions are intentionally not provided.
- GitHub onboarding is bilingual: `README.md` / `README_RU.md`, Windows user guides and separate full macOS EN/RU guides cross-link each other.
