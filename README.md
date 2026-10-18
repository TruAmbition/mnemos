# Mnemos

**Your engineering work, made reusable.** Mnemos is a portable knowledge toolkit built around a dedicated Obsidian vault: capture work, find prior solutions, carry context between assistants, and turn verified documentation into repeatable task plans.

Start as one author with a team of readers. Add named author credentials when more engineers contribute. Markdown stays the source of truth, so the knowledge remains useful outside this application.

## Included in this version

- A Projects registry for local Git checkouts, with selected documentation, optional automatic refresh, source revisions, and preserved snapshot history.
- A standalone desktop build recipe, a Mac drag-to-Applications installer, and a launcher that reuses a background local service.
- A local connection dashboard with workspace targets, mismatch notices, local tests, and service stop controls.
- A searchable web library with document types, project filters, and draft/verified status.
- A separate Obsidian vault containing runbooks, knowledge items, troubleshooting, decisions, work logs, microtasks, and context handoffs.
- Five reusable assistant skills for capture, recall, file handoffs, workflow planning, and building new skills from documentation.
- Local MCP tools for compatible assistants, plus a cloud handoff page for exchanging reviewed context files without a tunnel.
- A CLI for capture, search, context recall, skill export, and dependency planning.
- Local or rclone cloud backup destinations, checksum-verified recovery, and an optional static reader export.
- Owner, author, and reader roles with revision checks on updates. Readers see verified documents; authors contribute drafts; the owner verifies them.
- Clearly labeled example documents and editable templates. Examples are not records of work performed in your infrastructure.

The application uses Python's standard library. It does not require a model API key, paid inference service, database server, or Obsidian community plugin. Your chosen assistant does the reasoning; Mnemos stores and retrieves the knowledge.

## Recreate this version with ChatGPT

Download the standalone [Mnemos 0.5.0 reconstruction prompt](prompts/rebuild-mnemos-v0.5.0.md) and attach the **entire file** to ChatGPT. It includes detailed setup/technical instructions, a Python recovery utility, and the verified application source snapshot with automatic project refresh. The embedded manifest identifies the exact commit and every included file. GitHub access and Git are not required to recover the source; Git is needed when using repository context.

The file is approximately 709 KiB because it carries the source itself, including the historical 0.3.0 prompt. Attach it rather than pasting the encoded payload. A chat with file/code tools can recover exact source bytes; a cloud chat returns files for you to run locally, while an authorized workstation agent can perform local setup. Text-only chats can guide you through the recovery utility. Python 3.11+ is required for source recovery/execution. Desktop binaries may differ by platform/build environment.

The frozen archive excludes private notes, credentials, machine configuration, Git history, and the reconstruction-prompt directory (to avoid recursively embedding older payloads). Its manifest verifies integrity, not publisher identity: use a trusted copy. Recover into a new folder to preserve existing installations. Historical prompts are retained in the repository but are not included in the new source capsule. The [0.3.0 prompt](prompts/rebuild-mnemos-v0.3.0.md) remains available for the pre-Projects baseline.

## Install and start

**Desktop app:** open the Mnemos disk image, drag the app to Applications, and open it. Python is bundled. The current local build is for Apple Silicon Macs and is ad-hoc signed, not notarized. See [desktop installation and connection management](docs/desktop-and-connections.md) for platform support, upgrading, and build instructions.

**Source checkout:** download this repository as a ZIP and extract it, or clone it using its actual GitHub URL. Install **Python 3.11 or later**, then double-click **start.command** on macOS or **start.cmd** on Windows. On Linux, run `python3 scripts/launch.py` from the repository folder.

The launcher opens the local portal. On first use, `/setup.html` guides you through the author name, a dedicated data folder, local or cloud backup storage, Obsidian detection/installation, and an assistant mode. Choose **local tools**, **cloud file handoff**, or an optional **existing connection**. Choosing a mode does not create a cloud account connection. Setup shows the appropriate assistant commands and portable skill options; it preserves unrelated assistant settings.

The normal launcher keeps the service running in the background; no terminal window needs to stay open. Reopen the same launcher to return to the running library. Use **Connections → Stop local service** to stop it. The setup header also offers a stop control before initialization. `--foreground` retains terminal diagnostics. Open [local setup](http://127.0.0.1:4318/setup.html) later to review installation choices. The terminal workflow remains available:

```sh
python3 scripts/setup.py
python3 scripts/install_agents.py --client both
python3 -m mnemos serve
```

On Windows, use `py -3` in place of `python3` if that is your Python launcher. Open [the local library](http://127.0.0.1:4318).

Each installation has **one active default workspace**. Packaged builds keep their initial data folder in the user's application-data directory outside the app; source checkouts retain `data/`. Reopen setup to update it, create a separate workspace, or select an existing initialized one. Applying a different workspace changes the default recorded in `data/installation.json`; it preserves the previous workspace's files, notes, and credentials. It does not copy or merge libraries. Commands without `--data` use this selected default, independent of the terminal's current directory; before any selection, they use this checkout's `data/` folder.

An explicit `--data /absolute/path/to/private-data` pins that command to the supplied workspace and stays outside default switching. Installed Codex, Claude, and tunnel connections also contain explicit paths: changing the default does **not** move, retarget, or disconnect them. Use **Connections** to see each identified target and test its local tools. A healthy connection can still point to a different workspace. A manually configured MCP server without `--data` stops accepting calls after the default changes and must be restarted. See [connection scope](docs/assistant-connections.md#workspace-selection-and-pinned-connections).

Setup creates a dedicated `vault` inside your chosen data folder (`data/` in this checkout by default). It checks for Obsidian and lets you request installation if it is missing. The optional terminal setup also asks for your author name and backup choice. It prefers Homebrew on macOS, winget on Windows, or Flatpak on Linux. When no supported package manager is available, it uses an official release download: DMG on macOS, EXE on Windows, or AppImage on Linux. If installation fails, it explains the result and points to the [official Obsidian download](https://obsidian.md/download). It does not silently report a failed install as complete.

The assistant setup step adds project-scoped connections and skills for Codex and Claude Code. Use `--client codex` or `--client claude` to select one, or omit that step for browser-only use. Reopen the project and accept its normal trust prompts in the chosen client. Existing unrelated settings are preserved; conflicting Mnemos entries are reported instead of overwritten.

Open the `vault` inside your selected data folder in Obsidian using **Open folder as vault**. Choose a new data directory outside any existing vault. Mnemos does not add plugins to, merge into, or change your other Obsidian vaults. Obsidian keeps notes and vault-specific settings in each vault's folder. [Obsidian storage documentation](https://obsidian.md/help/data-storage)

For a server that does not need the Obsidian desktop app:

```sh
python3 scripts/setup.py --author "Your name" --skip-obsidian
```

Keep your private library out of the public source repository. The default `data/`, `backups/`, and `exports/` directories are ignored by Git. If you choose a custom location inside the repository, add that location to `.gitignore` before committing. A private data directory outside the source checkout is also supported.

## Register your engineering projects

Open **Projects**, add an existing local Git checkout, and choose which documentation paths to include. **Refresh project context** creates a draft snapshot of committed sources, with commit/blob references and changed paths since the previous refresh. Existing notes and repository files remain intact. Recall prefers the latest captured snapshot; earlier snapshots remain searchable. No tunnel is required.

Each project has an **Automatic refresh** on/off switch, off by default. Enabled repos are checked about every 60 seconds while the local Mnemos service runs; new commits create new draft snapshots. Manual refresh remains available. Capture reads committed `HEAD` only; it does not pull remote changes or import uncommitted work. Review excerpts before sharing them. See [Projects and project context](docs/projects.md) for setup, limits, CLI usage, and privacy boundaries.

## Document work and resume it later

With the capture skill available to an assistant, ask:

> Document this work in Mnemos. Preserve why we made these decisions, the repeatable steps, and the checks we actually ran. Save a draft and link the evidence.

For a handoff between ChatGPT, Claude, and Codex:

> Export this task's context to Mnemos: goal, current state, constraints, decisions, failed approaches, unknowns, and next actions. Keep it concise and source-backed.

An authorized local MCP client can save directly, and an assistant with actual access to the installation can use the CLI. For cloud chats, the [Cloud handoff page](docs/cloud-handoff.md) exports selected context and accepts a reviewed draft JSON when you return. No tunnel is needed for local clients or this file workflow:

```sh
python3 -m mnemos capture --file /path/to/capture.json
python3 -m mnemos search "deployment"
python3 -m mnemos get --id document-id
python3 -m mnemos recall "deployment" --budget 6000
```

See the [capture format](skills/mnemos-capture/references/capture-format.md). Existing-document updates require their current revision. Recall returns a bounded context bundle with source IDs and revisions; the budget is characters, not tokens. The token estimate is approximate. Search and recall currently use keywords.

Mnemos does not automatically access every previous conversation or monitor all work. Export only the relevant accessible evidence; missing facts stay unknown. Use the [file handoff](docs/cloud-handoff.md) when a cloud chat has no vault connection. Review company policies before uploading source files. Optional existing [Secure MCP Tunnel](docs/chatgpt-tunnel.md) and [GPT Actions](docs/cloud-chatgpt.md) integrations remain available; they are separate from ordinary local setup.

## Connect your assistant

Start with local tools. Use [file handoff](docs/cloud-handoff.md) for explicit source selection in cloud tasks; consider a tunnel for frequent authorized ChatGPT lookup and draft updates. Local clients need no tunnel, but may still use cloud models. Read [the tunnel benefits and tradeoffs](docs/chatgpt-tunnel.md#is-a-tunnel-worth-it), including its access to all dedicated-vault notes and drafts, before choosing.

For direct Claude Desktop chats, use the [Claude Desktop installer](docs/claude-desktop.md). It connects this vault to the desktop app and preserves existing settings. Browser-based Claude uses a separate remote connection.

For ChatGPT or Claude cloud chats, start with [portable context handoffs](docs/cloud-handoff.md). Download the context you choose, supply the `mnemos-handoff` skill, and import its returned draft locally. A skill alone does not grant direct access to your Mac.

The bundled skills live in `skills/`:

| Skill | Use it for |
| --- | --- |
| `mnemos-capture` | Document work or export context with provenance and secret redaction. |
| `mnemos-recall` | Retrieve relevant prior work and handoff context before continuing. |
| `mnemos-handoff` | Use supplied context files and return one draft JSON for local review. |
| `mnemos-orchestrate` | Build source-backed dependency plans and bounded microtasks. |
| `mnemos-build-skill` | Turn established knowledge into a scoped, reusable assistant skill. |

Use `python3 scripts/install_agents.py --client both` to configure this checkout, or add `--project /absolute/path/to/working-project` to configure another chosen workspace. The installer creates project-local settings and copies skills; it does not change global client settings. For manual Codex discovery, copy selected skill folders into the project's `.agents/skills/` directory, preserving existing skills. [Official skill discovery guidance](https://learn.chatgpt.com/docs/build-skills)

To install only portable skills, without initializing a vault or adding MCP settings, run:

```sh
python3 scripts/install_agents.py --skills-only --client both
```

The [Cloud handoff page](docs/cloud-handoff.md) also downloads `mnemos-skills.zip` containing bundled skill source only.

The local MCP server starts with:

```sh
python3 scripts/mcp_server.py --data /absolute/path/to/private-data
```

A local MCP client starts that process and communicates over standard input/output. See [assistant connections](docs/assistant-connections.md) for Codex and Claude Desktop configuration and tool names. Direct local clients require authorized access to the installation; cloud file handoffs require only the source material you choose to provide.

## Share with readers and add authors

The default loopback server treats local access as the owner. For a shared computer, use `--require-auth` and an owner token. Create credentials from the host:

```sh
python3 -m mnemos token --role reader --author "Engineer name"
python3 -m mnemos token --role author --author "Contributing engineer"
```

Give each person their own credential through an appropriate private channel. Tokens are shown when created; keep them out of source control and documentation. Author credentials can contribute drafts. The owner reviews and verifies content before readers can see it. Updates reject stale revisions instead of silently replacing a newer edit.

For remote readers, run on a controlled host behind HTTPS and an access-controlled network. A reverse-proxied instance **must** use `--require-auth`; otherwise a loopback proxy would inherit local-owner access:

```sh
python3 -m mnemos serve --data /absolute/path/to/private-data \
  --host 127.0.0.1 --port 4318 --require-auth \
  --public-host knowledge.example.com
```

Replace the illustrative hostname with your actual hostname, preserve the incoming Host header through the proxy, and keep the application port private. If using direct private-network binding, specify the bind address and the exact hostname including port with `--public-host`. This is a lightweight application, not a managed identity platform; see [deployment and storage](docs/deployment.md) for the current boundaries.

## Back up, recover, and export

Choose local storage or a preconfigured rclone remote in setup or the owner's storage settings. For cloud backup, install rclone and configure the desired provider separately. Use an rclone crypt remote when client-side encryption is required; the local snapshot itself is not encrypted.

```sh
python3 scripts/backup.py
python3 scripts/restore.py /path/to/mnemos-snapshot.zip --to /path/to/empty-recovered-vault
```

Backups contain vault files and a checksum manifest. They do not contain installation settings or access tokens. Restore verifies the manifest and requires a new or empty destination. It restores a **vault folder**, not a fully configured installation. Follow the [recovery procedure](docs/deployment.md#recovery-test) to start a recovered library. Cloud backup is not live synchronization between multiple writers.

An optional static website can be generated from verified documentation:

```sh
python3 scripts/export_reader.py --out ./exports/reader
```

The export is unencrypted and has no application login. Host it only where the audience is authorized to read every included document. **Do not publish private documentation to public GitHub Pages.** The toolkit source may be public while the runtime library stays private.

## Plan repeatable work

The example workflow demonstrates evidence review, draft capture, and verification:

```sh
python3 -m mnemos workflow-plan --id first-capture
```

A workflow references source documents, declares dependencies, and marks approval checkpoints. The planner checks missing sources, missing dependencies, and cycles. It returns an ordered plan with source revisions. **It does not execute the tasks.** The orchestration skill guides an assistant through separately authorized work with evidence and stop conditions.

## Name and existing installations

The product and canonical Python package are **Mnemos**. Use `python3 -m mnemos`; the previous `python3 -m keystone` entry point remains a compatibility alias. Existing checkout folders may still be named `keystone` so configured absolute paths keep working. Do not rename the folder solely to change the product name.

Project installers reuse matching legacy `keystone` MCP entries without adding a duplicate. The Claude Desktop installer can rename an equivalent entry to `mnemos` only when applied, with a backup. Stable backup manifest names, storage locks, and existing tunnel profile identifiers deliberately retain their legacy names for compatibility. No existing key or tunnel must be replaced just for the rename.

## Develop and contribute

Run from the source checkout:

```sh
python3 -m unittest discover -s tests -v
```

See [validation notes](docs/validation.md) for the checks performed on this release and the boundaries that still require your environment.

The GitHub Actions workflow runs the test suite across Linux, macOS, and Windows. It does not deploy a library or upload private vault contents. Keep implementation changes separate from private data, use the seed vault for non-sensitive examples, and document behavior changes in the relevant guide. See [architecture and roadmap](docs/architecture.md) for extension points and current limitations.

Released under the [MIT license](LICENSE).
