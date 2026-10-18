# Native macOS manager

Mnemos now includes a real SwiftUI management app alongside its HTML documentation interface. The native window and browser manage the same Python service, workspace selection, and Markdown vault. The Mac bundle includes Python; users do not need Xcode or a Python installation to run it.

Version 0.8.1 simplifies the dashboard and moves occasional controls into expandable sections. See [focused workspace](focused-workspace.md).

## Use the app

Open **Mnemos.app**. The manager starts its local service when needed. A fresh installation opens **Workspace** setup. If another Mnemos installation already uses port 4318, the app identifies its workspace and offers **Manage this installation**. Accepting remembers that installation locally without copying its notes or changing assistant connections. It refuses to take over a pinned or externally managed service. An unrelated application occupying the port is left alone; startup reports the conflict.

- **Overview:** active workspace, service status, start/stop, Open Library, Open in Obsidian, and Show vault in Finder.
- **Workspace:** change author, choose local tools/cloud file handoff/existing connection, configure local or rclone backups, and optionally install Obsidian. Create a new workspace or inspect and activate an existing one. Only one workspace is the active default for this installation. Activation keeps the previous workspace intact.
- **Backups:** show the saved destination, make a backup, and inspect recent results. Cloud upload failures retain their local snapshot. There is no automatic backup schedule in this version.
- **Projects:** review existing local checkouts and toggle automatic context refresh for each repo. Add projects or change source patterns through **Add or manage projects in Library**.
- **Assistants:** inspect existing local connection status and targets, run local checks, and read the tunnel/file handoff tradeoffs. Installation commands and portable skills remain in browser setup. Choosing an assistant mode does not install skills, connect an account, or start a tunnel.

**Open Library** uses your default browser for note editing, search, capture, recall, handoff, skill creation, and workflow planning. The native app is a management companion, not a replacement editor or WebView wrapper. Obsidian continues to provide graph and canvas views of the same vault.

Closing the native window or quitting the manager leaves the service running. Stop it explicitly from Overview → Service & installation or browser Connections. Stopping pauses local HTTP access and project refresh but does not stop independent MCP or tunnel processes. There is no login item or automatic startup at reboot.

The manager remembers the chosen installation in macOS preferences; vault settings remain in the workspace's existing configuration. Packaged defaults live under `~/Library/Application Support/Mnemos/data`. Explicitly pinned assistant connections stay pinned when the default changes. Use Reload after changes from another interface; it replaces unsaved form edits. Configuration writes include workspace and settings revisions, and selecting an existing workspace requires inspecting its settings first. Concurrent changes produce an error instead of overwriting the other window's choices.

## Build and test

Requirements for building: macOS, Xcode Command Line Tools with Swift 5.9 or newer, Python 3.11+, and the existing isolated PyInstaller environment. The Swift package has no third-party dependencies. The declared minimum is macOS 13; this build was exercised on Apple Silicon macOS 26.5. Older supported macOS and Intel builds need separate validation.

```sh
swift build --package-path desktop
python3 scripts/test_desktop.py
python3 -m unittest discover -s tests
node --test tests/web.test.cjs
python3 -m venv .venv-build
.venv-build/bin/python -m pip install pyinstaller==6.16.0
.venv-build/bin/python scripts/build_desktop.py --output desktop-output --work desktop-work --dmg
```

Use fresh build/output directories. `scripts/test_desktop.py` runs the Swift tests against a temporary real Python server and disposable workspaces, including create/update/select, backup retention, stale-workspace rejection, and stop. It never selects your real workspace. Plain `swift test --package-path desktop` skips that live-service case unless the test harness supplies its isolated environment. The GitHub macOS job runs the harness; Python and browser regression jobs still cover Windows, Linux, and macOS.

`swift build` alone compiles the manager but does not create a self-contained app. Use `build_desktop.py` for the runnable bundle. On macOS it now:

1. Builds the existing Python application and resource allowlist with PyInstaller.
2. Keeps the runtime at `Contents/MacOS/MnemosRuntime`.
3. Builds the SwiftUI executable and installs it as `Contents/MacOS/Mnemos`.
4. Sets normal foreground-app metadata, signs the full bundle ad hoc, and creates ZIP/DMG artifacts.

Existing connections pointing at `Contents/MacOS/Mnemos --tool …` or `--cli …` remain supported: the Swift entry point replaces itself with the Python helper, preserving arguments, standard input/output, and exit status. Newly generated connections can reference the helper directly. Keep the complete app at a stable installed path.

The native HTTP client connects only to `127.0.0.1`, uses ephemeral sessions, bypasses proxies, refuses redirects, and submits workspace markers on mutations. It reads sanitized setup/connection responses, not assistant credentials. The app does not listen on a network port of its own.

For development, the app accepts `--port <fixed-port>` and `--installation /absolute/path/to/installation.json`. The Python launcher accepts the same installation option, mutually exclusive with `--data`. An installation pointer follows default switches; `--data` remains pinned. This is not remote-server management.

The build is ad-hoc signed and not Apple notarized. Signing, enterprise deployment approval, and notarization remain distribution tasks. Windows/Linux retain their existing browser launchers; SwiftUI is macOS-only. The published 0.7.1 download does not include this manager; use a 0.8.0 build.
