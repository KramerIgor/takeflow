# Takeflow for macOS

**English** | [Русский](MACOS_USER_GUIDE_RU.md)

## Installation

1. Open the current Takeflow GitHub Release.
2. Download `AppleSilicon.dmg` for an M1/M2/M3/M4 or newer Mac, or `Intel.dmg` for an Intel Mac.
3. Open the downloaded DMG.
4. Drag **Takeflow** to the **Applications** shortcut.
5. Open Takeflow from Applications.

Python, Homebrew, Node.js and Git are not required.

## First launch on an unsigned beta

Takeflow is ad-hoc signed but is not registered or notarized by Apple. macOS will normally block its first launch.

1. Try to open Takeflow once and close the warning.
2. Open **System Settings → Privacy & Security**.
3. Scroll to **Security** and click **Open Anyway** for Takeflow.
4. Confirm **Open** and enter the Mac login password if requested.

This creates a one-app exception. Do not disable Gatekeeper globally and do not run downloaded shell commands to bypass it. Compare the DMG SHA-256 with the `.sha256` file attached to the same GitHub Release.

Apple documents this flow in [Open a Mac app from an unknown developer](https://support.apple.com/guide/mac-help/mh40616/mac).

## Local data

- Settings and history: `~/Library/Application Support/Takeflow`
- Launcher logs: `~/Library/Logs/Takeflow/launcher.log`
- Default projects: `~/Movies/Takeflow`

The **Projects** screen can select another writable project root. Takeflow never moves existing projects automatically.

## Updates

Takeflow selects the update asset for the current Mac architecture. After downloading a DMG, it opens in Finder; replace the existing app in Applications after closing Takeflow.
