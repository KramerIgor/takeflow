# Takeflow User Guide

**English** | [Русский](USER_GUIDE_RU.md)

This guide is for people installing and using Takeflow on Windows without a development environment.

## Requirements

- Windows 10 or Windows 11, 64-bit
- A modern browser
- Internet access for Segmind requests
- A Segmind API key and sufficient account balance for paid generation
- At least 250 MB of free disk space for the application
- Additional disk space for generated videos and project files
- Local port 7860 available

The installer is approximately 20 MB. The installed application is approximately 45 MB before user data and generated media.

## Install

1. Open the [Takeflow 0.1.3 beta release](https://github.com/KramerIgor/takeflow/releases/tag/v0.1.3-beta).
2. Download TakeflowSetup-*.exe.
3. Run the downloaded installer.
4. Choose the installation folder.
5. Leave **Create a desktop shortcut** enabled if desired.
6. Finish the installation and launch Takeflow.

The current beta is not digitally signed. Windows SmartScreen may display an unknown publisher warning. Verify that the installer came from the official KramerIgor/takeflow release and compare its SHA-256 checksum with the release notes before continuing.

## Start and Stop

Start Takeflow from:

- the desktop shortcut;
- the Start Menu entry;
- Takeflow.exe in the installation folder.

Takeflow starts a local server and opens http://127.0.0.1:7860. It does not expose the application to the public internet by default.

Use **Quit / Выход** in the top bar to stop the local server. Takeflow attempts to close its tab; if the browser blocks that action, the final screen confirms that the tab can be closed safely.

## First Setup

Open **Projects / Проекты**.

1. Paste your Segmind API key.
2. Confirm the API base URL.
3. Select the default Seedance model.
4. Keep the default `outputs/MyFirstProject` folder next to the installed app or choose another output root using **Choose / Выбрать**.
5. Create or select a project folder.

Takeflow does not move existing project folders when the output root changes.

Never share screenshots containing an API key. Takeflow does not display the saved key after it is stored.

While a generation is active, the History rail refreshes automatically without replacing the form. Its progress indicator is an estimate based on recent completed runs, not an exact value reported by Segmind.

## Single Generation

1. Open **Single Generation / Одиночная генерация**.
2. Optionally enter a generation name.
3. Enter the prompt.
4. Attach references using the Add tile or drag and drop.
5. Select model, duration, resolution and aspect ratio.
6. Review the local cost estimate.
7. Press the paid generation button.
8. Read and confirm the paid-action dialog.

The task appears in the right-side history while it is processing. Refreshing history does not clear the current prompt.

## References

- Current Seedance 2.0 Base, Mini and Fast configurations allow up to 9 attached files.
- The limit is model-specific and may differ for future models.
- Image references are submitted through the supported API workflow.
- Video and audio files can be stored with task history even when the current API path does not submit them.
- Type @ in the prompt to insert an attached reference token.
- Remove a reference using the cross shown on its preview.

Do not rename or move a local reference while a queued task still depends on it.

## Queue

Use **Queue / Очередь** to prepare several tasks before processing:

1. Add tasks to the queue.
2. Review each task and its estimate.
3. Edit or remove queued items if needed.
4. Start the paid queue only when the complete list is correct.

Queue history appears in the right rail. Details remain collapsed until opened.

CSV import can validate a batch without creating paid requests. Preview the CSV first, then confirm task creation. Creating queue tasks does not itself start paid generation.

## History

History cards provide:

- status and progress;
- prompt and references;
- selected generation settings;
- estimated or reported cost;
- output preview and folder access;
- edit and regenerate actions.

**Regenerate** creates a new paid request after confirmation. It does not overwrite the previous result.

## Cost and Balance

The pre-submit value is an estimate based on known public pricing and selected parameters. The final provider charge may differ. If Takeflow cannot safely determine a price, it displays no estimate instead of inventing one.

Always verify the paid confirmation and current Segmind account balance before submitting.

## Updates

Takeflow checks the public update.json manifest. It does not update through git pull.

When a newer release is available:

1. Start the download from the update panel.
2. Wait until progress reaches 100%.
3. Confirm installer launch.
4. Complete the installer.

An installer is never launched without user confirmation.

## Troubleshooting

### Browser does not open

Open http://127.0.0.1:7860 manually.

### Port 7860 is already in use

Close another Takeflow instance. If needed, use Task Manager to end only the old Takeflow.exe process.

### Takeflow does not start

Check:

~~~text
%LOCALAPPDATA%\Takeflow\logs\launcher.log
~~~

Do not publish this log without checking it for local paths or other private information.

### Generation fails

- confirm the API key;
- check the Segmind balance;
- verify internet access;
- ensure reference files still exist;
- open task details and read the displayed error.

Do not repeatedly confirm paid generation while the provider status is uncertain.

## Uninstall

Use **Windows Settings → Apps → Installed apps → Takeflow → Uninstall**.

Generated projects are stored under the output root selected by the user. Review that folder separately; uninstalling Takeflow is not intended as a project deletion workflow.

## Privacy and Paid Actions

Takeflow stores its GUI state locally. Prompts, references and generation parameters sent for generation are processed by Segmind according to its service terms.

Paid requests are never part of diagnostics, browser checks or automatic startup. A user confirmation is required before generation begins.
