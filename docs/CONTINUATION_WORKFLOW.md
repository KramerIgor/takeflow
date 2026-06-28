# Stage 8 continuation workflow

Updated after Stage 8 completion baseline.

## Correct workflow for this project

The project should NOT use the previous video's last frame as a strict first_frame_url by default.

The required automatic queue-first workflow is:

    previous generated video
    -> API returns video.last_frame_url
    -> worker downloads it to runs/<take>/last_frame.png
    -> child continuation task waits for parent completion
    -> worker uploads parent last_frame.png through existing Segmind upload_asset
    -> returned image URL is added to reference_images of the next generation
    -> worker submits the child generation

So the previous last frame becomes one of the reference images for the next clip.

Manual Continue from previous take remains only a secondary/debug fallback. It is not the main continuation workflow.

## Why

The user wants the next video to be guided by the previous video's final frame, not forced to start from it exactly.

This allows the next prompt to continue the scene while still keeping flexibility and allowing additional character/location/style references.

## Current confirmed API fact

A paid test confirmed:

    return_last_frame=true

returns:

    video.last_frame_url

The worker saves it as:

    Project/runs/<take_stem>/last_frame.png

## Current confirmed backend behavior

Backend queue chaining dry-run passed:

    RESULT=STAGE8_BACKEND_CHAINING_DRY_RUN_OK

Real paid continuation test passed:

    Parent task id: 25
    Child continuation task id: 26
    Child status: completed
    Child output: /mnt/c/AI_OUTPUT/Psailor_kun/videos/Episode_00_Scene_998_LastFrame_API_Test_take_000002.mp4
    Child run dir: /mnt/c/AI_OUTPUT/Psailor_kun/runs/Episode_00_Scene_998_LastFrame_API_Test_take_000002
    Child last frame: /mnt/c/AI_OUTPUT/Psailor_kun/runs/Episode_00_Scene_998_LastFrame_API_Test_take_000002/last_frame.png

Confirmed behavior:

- Parent last_frame.png is used as a child reference image through existing upload_asset.
- The uploaded URL is appended to child reference_images.
- first_frame_url is not the default workflow.

## Current Stage 8 result

Stage 8 is complete as a working baseline.

Chain Builder route still exists as a backend/queue capability, but Continuation Chain is not a primary tab in the current product UI.

Chain Builder route:

    POST /add-continuation-chain

Chain Builder behavior:

- Creates queued tasks only.
- Does not start paid generation.
- First task is independent.
- Child tasks use continuation_mode=last_frame_as_reference.
- Child tasks point to the previous created task with parent_task_id.
- All chain tasks use return_last_frame=True.

GUI smoke-test passed:

    RESULT=STAGE8_CHAIN_BUILDER_GUI_SMOKE_TEST_OK

Test chain was cancelled safely:

    tasks #27, #28, #29 cancelled
    queued_count=0

## Correct continuation payload direction

Main continuation direction:

    reference_images = [uploaded_parent_last_frame_url, ...other_reference_images]

Do not make first_frame_url the default continuation mechanism. Do NOT use previous last_frame as first_frame_url by default.

first_frame_url may be kept only as a future optional alternative mode if the user explicitly wants exact frame-to-frame continuation.

## Current GUI state

The current primary GUI tabs are:

- Projects.
- Single Generation.
- History.
- Queue.

Current status:

- Product UI is active, not just presentation-only.
- Worker backend chaining is validated.
- DB schema and API client are unchanged.
- Continuation Chain is not a primary tab; chain creation remains available through backend/queue capability.
- Manual Continue from previous take remains inside Queue row Debug / files as secondary/debug fallback.

## Parked items

- Parallel queues.
- Cost limits.

## Related Stage 9 status

Stage 9 CSV batch import is complete as a working baseline.

Batch import creates queued tasks only and does not start paid generation.

CSV rows can opt into continuation chaining with continuation_group and continuation_index. Rows in the same group are linked in CSV order; each child waits for the previous task and uses its last_frame.png as a reference image.

The import path does not use first_frame_url.

## Related Stage 10 status

Stage 10 Night Mode Safety Preview is complete as a working baseline.

The preview only plans a safe queue run. It does not start paid generation and does not run dependent continuation chains in parallel.

## Important rule

Do not redo the API client. Upload asset, submit, polling and result fetch already exist.

Stage 8 should now return to GUI work.
