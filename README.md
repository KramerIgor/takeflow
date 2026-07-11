# Takeflow

**English** | [Русский](README_RU.md)

**Takeflow — локальная AI-video студия для сцен, дублей и очередей, созданная Игорем Олеговичем Крамером / IOKRAMER.**

Takeflow is a local Windows and macOS desktop interface for organizing projects and generating video through the Segmind Seedance API. The application opens in the browser and keeps project files on the user's computer.

Current release: **0.1.3 beta** (v0.1.3-beta).

## Download for Windows

Download the latest installer from [Takeflow 0.1.3 beta](https://github.com/KramerIgor/takeflow/releases/tag/v0.1.3-beta):

1. Download TakeflowSetup-*.exe.
2. Run the installer.
3. Keep the desktop shortcut enabled.
4. Start Takeflow from the desktop or Start Menu.

Python, Node.js, npm and Git are not required for the installed application. The current beta installer is unsigned, so Windows SmartScreen may ask for confirmation.

See the complete [English User Guide](docs/USER_GUIDE.md) or [Russian User Guide](docs/USER_GUIDE_RU.md).

## Download for macOS

The GitHub Release provides two ready-to-run disk images:

- `Takeflow-*-macOS-AppleSilicon.dmg` for M1, M2, M3, M4 and newer Apple chips.
- `Takeflow-*-macOS-Intel.dmg` for Intel Macs.

Open the DMG and drag **Takeflow** to **Applications**. Python, Homebrew, Node.js and Git are not required. Because this educational beta is not registered with Apple, the first launch requires the one-time **System Settings → Privacy & Security → Open Anyway** confirmation. See the [macOS User Guide](docs/MACOS_USER_GUIDE.md).

## What Takeflow Does

- Manages independent video projects and output folders.
- Runs single Seedance generations with a compact history rail.
- Builds and processes generation queues.
- Runs queues sequentially or in bounded parallel waves (1-10 independent jobs); continuation chains preserve parent-first order.
- Imports queue tasks from CSV.
- Supports image, video and audio reference attachments in the UI.
- Provides model-aware duration, resolution and reference limits.
- Shows a local pre-submit cost estimate where public pricing is available.
- Refreshes active history automatically without clearing the prompt and shows estimated generation progress.
- Supports Russian and English UI.
- Requires explicit confirmation before paid generation.

Takeflow itself is local, but video generation uses the external Segmind API and may incur charges.

## First Run

1. Open **Projects**.
2. Enter a Segmind API key.
3. Keep the default `outputs/MyFirstProject` folder next to the Windows app, or select another writable output root.
4. Create or select a project.
5. Open **Single Generation** or **Queue**.

The API key is stored locally and is excluded from Git. Never publish the local .env file.

## Development

Windows development requirements:

- Windows 10 or Windows 11, x64
- Python 3.12
- Git

Setup:

~~~powershell
git clone https://github.com/KramerIgor/takeflow.git
Set-Location -LiteralPath '.\takeflow'
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
Copy-Item '.env.example' '.env'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 7860
~~~

Open http://127.0.0.1:7860.

Safe diagnostics:

~~~powershell
& '.\.venv\Scripts\python.exe' -m compileall app scripts takeflow_launcher.py
& '.\.venv\Scripts\python.exe' -u scripts\check_takeflow_release.py
& '.\.venv\Scripts\python.exe' -u scripts\check_release_readiness.py
~~~

These checks use dry-runs and synthetic data. They must not submit paid generation requests.

## Windows Installer Build

Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) and PyInstaller in the project virtual environment, then run:

~~~powershell
& '.\.venv\Scripts\python.exe' -m pip install pyinstaller
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\build_windows_installer.ps1'
~~~

Output:

~~~text
dist\installer\TakeflowSetup-0.1.3beta.exe
~~~

The build script also updates update.json with the release URLs and SHA-256 checksum.

## macOS Package Build

macOS packages must be built on macOS. GitHub Actions runs the maintained Apple Silicon and Intel builds; local macOS contributors can run:

~~~bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pyinstaller
.venv/bin/python -m compileall app scripts takeflow_launcher.py
.venv/bin/python scripts/check_macos_release.py
.venv/bin/python -m PyInstaller --version
PATH="$PWD/.venv/bin:$PATH" bash scripts/build_macos_dmg.sh "$(uname -m)"
~~~

The app is ad-hoc signed for bundle integrity but is not Apple-notarized. Do not claim otherwise in release notes.

## Repository Guide

- [User Guide (English)](docs/USER_GUIDE.md)
- [Руководство пользователя (Русский)](docs/USER_GUIDE_RU.md)
- [macOS User Guide (English)](docs/MACOS_USER_GUIDE.md)
- [Руководство macOS (Русский)](docs/MACOS_USER_GUIDE_RU.md)
- [Agent and Contributor Guide](docs/AGENT_GUIDE.md)
- [Project State](docs/PROJECT_STATE.md)
- [Continuation Workflow](docs/CONTINUATION_WORKFLOW.md)
- [Agent Rules](AGENTS.md)

## Security and Privacy

The repository intentionally excludes:

- .env and API keys
- virtual environments and local runtimes
- SQLite databases and active project state
- generated videos, outputs and run archives
- logs, caches and temporary files
- downloaded models and checkpoints

Review staged files before every push. Do not place credentials in issues, screenshots, logs or release assets.

## Creator

Created by **Игорь Олегович Крамер / IOKRAMER**.

No open-source license has been declared yet. Public source availability does not by itself grant reuse or redistribution rights.
