# Desktop launch and connection management

Mnemos 0.8 adds a native SwiftUI Mac manager alongside the existing browser interface. The Mac app includes Python and requires no inference API key or tunnel for local use. See [native macOS management](native-macos.md) for its screens, existing-installation detection, build requirements, and validation. Version 0.7.1 was the earlier browser launcher; Windows/Linux keep that launcher design.

## Install the desktop app

Download the Apple Silicon DMG or app ZIP from [GitHub Releases](https://github.com/TruAmbition/mnemos/releases/latest). Version 0.8.0 includes native Mac management, Getting started, and skill matching. The release also includes source and a standalone reconstruction prompt.

On macOS, open the disk image, drag **Mnemos.app** into **Applications**, eject the disk image, then open Mnemos. Keep the app in its installed location: assistant connections may refer to its executable. The first start can take around 30–40 seconds while macOS loads the bundle. Subsequent opens reuse the running local service.

The supplied build targets **Apple Silicon** and was tested on macOS 26.5. It is ad-hoc signed, **not Apple Developer ID signed or notarized**. Organization-managed devices may require IT approval. This is a developer distribution, not a universally trusted public release. Do not disable system protections to install it.

The repository includes a manually triggered **Desktop bundles** GitHub Actions workflow for macOS, Windows, and Linux. Windows builds include **Open Mnemos.exe** beside the console-capable **Mnemos.exe** runtime and `_internal` folder. Linux builds include a `Mnemos` executable. Extract the whole archive and keep its contents together. Those platforms' packaged launchers have not been executed in the local Mac validation; build and test on the target OS before distributing them.

## Start, reopen, and stop

- On macOS 0.8+, open the app for the native manager, then choose **Open Library** for the browser. Earlier Mac and Windows/Linux packages open the local service and browser. First use opens Workspace setup. After setup, the first visit in a browser opens Getting started; later root launches open the Library. Explicit page links keep their destination.
- Opening the same launcher again reuses its existing service. Closing a browser tab does not stop Mnemos.
- Use **Connections → Stop local service**, or **Stop local service** in the setup header. Reopen the app to start again. Notes remain on disk.
- A port occupied by a different Mnemos installation is reported rather than silently switching the user to that library. A different app on the port is left alone. Stop the intended Mnemos service from its own page, or use a different port.
- The portal is separate from assistant-launched MCP processes and the optional tunnel. Stopping the portal does not stop those connections.
- This version does not install login items or system services. Start it after reboot by opening the app.

The source checkout still supports Python 3.11+ with `start.command`, `start.cmd`, or `python3 scripts/launch.py`. Normal launch now detaches the local service; the terminal is not required to remain open. Use `--foreground` for terminal diagnostics, `--no-browser` for a foreground automation process, or `--background --no-browser` for a detached process without opening a browser. `--port` defaults to 4318. Diagnostic logs are private and overwritten on the next start in `.mnemos-runtime` beside the default data directory (or beside a pinned data directory).

## Data stays outside the app

| Distribution | Initial data folder |
| --- | --- |
| Source checkout | `data/` inside the checkout |
| Packaged macOS | `~/Library/Application Support/Mnemos/data` |
| Packaged Windows | `%LOCALAPPDATA%\Mnemos\data` |
| Packaged Linux | `$XDG_DATA_HOME/mnemos/data`, or `~/.local/share/mnemos/data` |

Each installation records one active default in its initial data folder's `installation.json`. Workspace setup can create a new default or select an existing initialized workspace. Old libraries stay intact. Replacing the app does not replace the data folder. Explicit `--data` connections remain pinned.

**Moving from the source checkout:** stop its local portal, open the packaged app, then choose **Use an existing workspace** and select the source checkout's existing `data` directory. This selects that library without copying or merging notes. The two launchers have separate default selections; use one launcher consistently. Existing assistant connections remain tied to their configured commands and paths. Keep the old checkout until those connections are deliberately reconfigured.

Packaged Codex/Claude Code setup commands require a project folder. Replace `path-to-your-project` in the displayed command before running it. The app never installs skills into its own bundle. Claude Desktop setup still preserves unrelated settings and performs its normal preflight. No setup action silently retargets existing connections.

## Read the Connections dashboard

The dashboard is available only to the local owner, not network readers or shared authenticated servers. It inspects Codex user settings, the selected project's Codex and Claude Code settings, Claude Desktop's standard configuration location on macOS/Windows, and tunnel profiles in the active/default/configured workspaces. It does not scan every project or inspect cloud account settings. Managed configuration layers, arbitrary command wrappers, and remote MCP URLs are not resolved automatically.

| Status | Evidence |
| --- | --- |
| Configured | A recognizable local connection and workspace were found; no successful local test is recorded in this service session. |
| Tested locally | A local check passed at the displayed time. This is a snapshot, not continuous monitoring or cloud account verification. |
| Disconnected | No configured connection was found, it is disabled, or the tunnel's local readiness test failed. |
| Needs attention | Configuration, launcher, workspace validation, or a local tool test failed. |

Every identified workspace is compared to the active library. **Uses a different workspace** is independent of connection status: a connection may be healthy while intentionally pointing to an older library. Switching the default does not retarget it.

**Test locally** for a local assistant uses Mnemos's own trusted runtime against the configured workspace and checks MCP initialization/tool discovery. It does not execute arbitrary commands or inject environment variables found in assistant settings, read note contents, write a test note, or prove that the assistant app has loaded its configuration. For a tunnel it checks only the existing local `/healthz` and `/readyz` listener; it never requests a key. Verify the complete connection from the assistant by requesting recall and checking the returned source/workspace.

**Refresh configuration** rereads settings. It does not rerun connection tests. Test results stay in server memory, are invalidated when that connection's configuration or target changes, and reset on service restart. Settings and credentials are not returned to the browser; it receives status labels, paths, descriptions, and timestamps.

For headless inspection, use `python3 -m mnemos connections --project /absolute/project`. The packaged equivalent is the Mnemos executable followed by `--cli connections`. Output is sanitized configuration status; no tests or mutations run.

## Build a distribution

Use an isolated build environment on each target OS. macOS builds also require Swift 5.9+ through Xcode Command Line Tools; end users do not need Swift or Xcode. The application itself has no third-party Python dependencies; PyInstaller is only a build dependency.

```sh
python3 -m venv .venv-build
.venv-build/bin/python -m pip install pyinstaller==6.16.0
.venv-build/bin/python scripts/build_desktop.py --output desktop-output --work desktop-work --dmg
```

Use the virtual environment's `Scripts\python.exe` on Windows; omit `--dmg` on Windows/Linux. Use fresh output and work folders for each build. The build includes only approved application resources, bundled tool scripts, and imported code. It excludes private data, connection settings, keys, and logs. The Mac disk image contains the app and an Applications shortcut. Developer ID signing/notarization and Windows signing require the distributor's credentials and are not configured here.

The bundle layout and executable dispatch follow [PyInstaller runtime guidance](https://pyinstaller.org/en/stable/runtime-information.html). Builds are native to the target OS; see [PyInstaller usage](https://pyinstaller.org/en/stable/usage.html).
