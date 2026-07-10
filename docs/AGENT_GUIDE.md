# Takeflow Agent and Contributor Guide

This document is the repository entrypoint for coding agents and contributors. Read AGENTS.md and docs/PROJECT_STATE.md before editing.

## Product Boundary

Takeflow is a local Windows and macOS GUI for Segmind Seedance video workflows. Preserve:

- Projects and output-root selection
- Single Generation and its history rail
- Queue and queue history
- compact cards and details disclosure
- pagination
- refresh without prompt loss
- drag/drop references and inline @ tokens
- edit and regenerate actions
- paid confirmation
- RU/EN localization
- model, resolution, duration and reference constraints

Do not reintroduce the removed Text-to-Audio module.

## Safety Rules

- Never read, print, stage or publish .env.
- Never call Segmind or another paid API during diagnostics.
- Never start a paid generation without explicit user confirmation.
- Never delete user outputs, videos, references, results, history or databases as cleanup.
- Do not modify C:\AI_OUTPUT or another configured output root during routine checks.
- Do not weaken confirmation dialogs or refresh guards.
- Treat external payloads, uploaded files and generated metadata as untrusted.
- Keep .venv, .runtime, dist, build, logs, databases and generated media out of Git.

## Architecture

~~~text
app/main.py                 FastAPI routes and Jinja context
app/db.py                   SQLite task/history persistence
app/queue_worker.py         generation worker and queue processing
app/segmind_client.py       external API boundary
app/costing.py              display-layer price estimates
app/storage.py              project/run/video path allocation
app/runtime_paths.py        platform-specific user data, environment and log paths
app/updater.py              platform-aware GitHub manifest and package download
app/version.py              canonical application version
app/templates/index.html    Jinja-rendered structure and JS config handoff
app/static/style.css        application styles
app/static/app.js           ES module entrypoint
app/static/js/              focused frontend modules
packaging/                  Windows and macOS PyInstaller plus Inno Setup definitions
scripts/                    diagnostics and release build scripts
~~~

Keep backend-generated technical values separate from localized display labels. Model ids, filenames, prompts and debug paths are not translated.

## Frontend Contracts

- window.seedanceConfig is the Jinja-to-JavaScript handoff.
- Existing data attributes and form names are regression-test contracts.
- The hidden prompt textarea remains the backend source of truth.
- Rich reference chips synchronize to tokens such as <@filename>.
- History refresh updates only the history rail and must preserve form state.
- Plain ES modules are preferred; do not introduce a build system or heavy framework without approval.

## Development Setup

~~~powershell
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
Copy-Item '.env.example' '.env'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 7860
~~~

Use a secret-free environment for checks. Do not copy a real API key into tests.

## Verification

Minimum safe pass:

~~~powershell
& '.\.venv\Scripts\python.exe' -m compileall app scripts takeflow_launcher.py
& '.\.venv\Scripts\python.exe' -u scripts\check_stage11_final_diagnostics.py
& '.\.venv\Scripts\python.exe' -u scripts\check_release_readiness.py
~~~

Frontend syntax:

~~~powershell
node --check app\static\app.js
node --check app\static\js\updates.js
node --check app\static\js\shutdown.js
~~~

Optional safe browser regression:

~~~powershell
& '.\.venv\Scripts\python.exe' -u scripts\check_frontend_browser_cdp.py
~~~

The browser check must stop before paid confirmation. Report skipped checks honestly.

## Change Discipline

1. Inspect git status -sb.
2. Read the relevant module and nearest regression check.
3. Make the smallest coherent change.
4. Run focused checks.
5. Run consolidated diagnostics.
6. Review the diff for accidental paths, secrets and generated artifacts.
7. Stage explicit files when unrelated work exists.

Do not mass-format the repository or rename internal Seedance integration identifiers for branding.

## Release Process

Canonical version values live in app/version.py.

~~~powershell
& '.\.venv\Scripts\python.exe' -m pip install pyinstaller
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\build_windows_installer.ps1'
~~~

Before publishing:

1. Run full diagnostics.
2. Confirm the packaged app answers /health.
3. Confirm no .env, database, output or generated media is staged or packaged.
4. Confirm update.json version, release URL, installer URL and SHA-256.
5. Commit source and manifest.
6. Push the release commit.
7. Create the exact tag from APP_RELEASE_TAG.
8. Create a GitHub Release and attach the matching installer.
9. Verify the public asset URL and checksum.

End-user updates use the GitHub update.json manifest. Never implement updates with git pull.

### macOS

- Build macOS packages only on macOS runners; PyInstaller output is OS-specific.
- Maintain both `macos-arm64` and `macos-x64` assets.
- Runtime state belongs in `~/Library/Application Support/Takeflow`, never inside `Takeflow.app`.
- The unsigned educational build uses ad-hoc codesigning and must not be described as notarized.
- `scripts/build_macos_dmg.sh` must produce a DMG, SHA-256 file and a bundle that passes `codesign --verify` plus `/health` smoke testing.
- Publishing is handled by `.github/workflows/build-macos.yml` after an existing release tag is supplied explicitly.

## Documentation Ownership

- README.md: public overview and developer quick start
- README_RU.md: Russian mirror of the public overview and developer quick start
- docs/USER_GUIDE.md: normal Windows user workflow
- docs/MACOS_USER_GUIDE.md: normal macOS install, Gatekeeper and update workflow
- docs/MACOS_USER_GUIDE_RU.md: Russian macOS install, Gatekeeper and update workflow
- docs/AGENT_GUIDE.md: coding-agent and contributor workflow
- AGENTS.md: mandatory repository-local operational rules
- docs/PROJECT_STATE.md: detailed implementation state and historical context

When behavior changes, update the smallest relevant document instead of duplicating instructions everywhere.
