# Keystone

**Your engineering work, made reusable.** Keystone is a portable knowledge toolkit built around a dedicated Obsidian vault: capture work, find prior solutions, carry context between assistants, and turn verified documentation into repeatable task plans.

Start as one author with a team of readers. Add named author credentials when more engineers contribute. Markdown stays the source of truth, so the knowledge remains useful outside this application.

## Included in this version

- A searchable web library with document types, project filters, and draft/verified status.
- A separate Obsidian vault containing runbooks, knowledge items, troubleshooting, decisions, work logs, microtasks, and context handoffs.
- Four reusable assistant skills for capture, recall, workflow planning, and building new skills from documentation.
- Local MCP tools for compatible assistants, plus a CLI for capture, search, context recall, and dependency planning.
- Local or rclone cloud backup destinations, checksum-verified recovery, and an optional static reader export.
- Owner, author, and reader roles with revision checks on updates. Readers see verified documents; authors contribute drafts; the owner verifies them.
- Clearly labeled example documents and editable templates. Examples are not records of work performed in your infrastructure.

The application uses Python's standard library. It does not require a model API key, paid inference service, database server, or Obsidian community plugin. Your chosen assistant does the reasoning; Keystone stores and retrieves the knowledge.

## Install and start

Download this repository as a ZIP and extract it, or clone it using its actual GitHub URL. Open a terminal in the extracted repository folder. Install **Python 3.11 or later**, then run:

```sh
python3 scripts/setup.py
python3 scripts/install_agents.py --data ./data --client both
python3 -m keystone serve --data ./data
```

On Windows, use `py -3` in place of `python3` if that is your Python launcher. Open [the local library](http://127.0.0.1:4318).

After setup, double-click `start.command` on macOS or `start.cmd` on Windows to start the local portal and open your browser. On Linux, run `python3 scripts/launch.py`. Keep its terminal window open while using the portal; Ctrl+C stops it. The launch shortcuts also run setup when the default data directory has not been initialized.

Setup asks for your author name and backup choice. It creates `./data/vault` as a dedicated vault, checks whether Obsidian is installed, and attempts installation through an available supported package manager when needed. It prefers Homebrew on macOS, winget on Windows, or Flatpak on Linux. When no supported package manager is available, it uses an official release download: DMG on macOS, EXE on Windows, or AppImage on Linux. If installation fails, it explains the result and points to the [official Obsidian download](https://obsidian.md/download). It does not silently report a failed install as complete.

The assistant setup step adds project-scoped connections and skills for Codex and Claude Code. Use `--client codex` or `--client claude` to select one, or omit that step for browser-only use. Reopen the project and accept its normal trust prompts in the chosen client. Existing unrelated settings are preserved; conflicting Keystone entries are reported instead of overwritten.

Open `data/vault` in Obsidian using **Open folder as vault**. Choose a new data directory outside any existing vault. Keystone does not add plugins to, merge into, or change your other Obsidian vaults. Obsidian keeps notes and vault-specific settings in each vault's folder. [Obsidian storage documentation](https://obsidian.md/help/data-storage)

For a server that does not need the Obsidian desktop app:

```sh
python3 scripts/setup.py --data ./data --author "Your name" --skip-obsidian
```

Keep your private library out of the public source repository. The default `data/`, `backups/`, and `exports/` directories are ignored by Git. If you choose a custom location inside the repository, add that location to `.gitignore` before committing. A private data directory outside the source checkout is also supported.

## Document work and resume it later

With the capture skill available to an assistant, ask:

> Document this work in Keystone. Preserve why we made these decisions, the repeatable steps, and the checks we actually ran. Save a draft and link the evidence.

For a handoff between ChatGPT, Claude, and Codex:

> Export this task's context to Keystone: goal, current state, constraints, decisions, failed approaches, unknowns, and next actions. Keep it concise and source-backed.

An assistant with a configured local MCP connection can save directly. An assistant with access to the checkout can use the CLI. A cloud chat without either connection can prepare a JSON file for import:

```sh
python3 -m keystone capture --data ./data --file /path/to/capture.json
python3 -m keystone search --data ./data "deployment"
python3 -m keystone get --data ./data --id document-id
python3 -m keystone recall --data ./data "deployment" --budget 6000
```

See the [capture format](skills/keystone-capture/references/capture-format.md). Existing-document updates require their current revision. Recall returns a bounded context bundle with source IDs and revisions; the budget is characters, not tokens. The token estimate is approximate. Search and recall currently use keywords.

Keystone does not automatically access every previous conversation, monitor all work, or grant a cloud chat access to local files. Export only the relevant accessible evidence. Missing facts stay unknown. For a private custom GPT, the supplied [ChatGPT Actions setup](docs/cloud-chatgpt.md) connects the existing API after you host and configure HTTPS and authentication. That connection is not deployed automatically; a remote MCP transport remains [future work](docs/architecture.md#roadmap).

## Connect your assistant

The bundled skills live in `skills/`:

| Skill | Use it for |
| --- | --- |
| `keystone-capture` | Document work or export context with provenance and secret redaction. |
| `keystone-recall` | Retrieve relevant prior work and handoff context before continuing. |
| `keystone-orchestrate` | Build source-backed dependency plans and bounded microtasks. |
| `keystone-build-skill` | Turn established knowledge into a scoped, reusable assistant skill. |

Use `python3 scripts/install_agents.py --data ./data --client both` to configure this checkout, or add `--project /absolute/path/to/working-project` to configure another chosen workspace. The installer creates project-local settings and copies skills; it does not change global client settings. For manual Codex discovery, copy selected skill folders into the project's `.agents/skills/` directory, preserving existing skills. [Official skill discovery guidance](https://learn.chatgpt.com/docs/build-skills)

The local MCP server starts with:

```sh
python3 scripts/mcp_server.py --data /absolute/path/to/private-data
```

An MCP client starts that process and communicates over standard input/output. It is not a website endpoint. See [assistant connections](docs/assistant-connections.md) for Codex and Claude Desktop configuration, tool names, and cloud handoff options. For hosted ChatGPT, use the prepared [Actions schema and setup guide](docs/cloud-chatgpt.md) after choosing your HTTPS host.

## Share with readers and add authors

The default loopback server treats local access as the owner. For a shared computer, use `--require-auth` and an owner token. Create credentials from the host:

```sh
python3 -m keystone token --data ./data --role reader --author "Engineer name"
python3 -m keystone token --data ./data --role author --author "Contributing engineer"
```

Give each person their own credential through an appropriate private channel. Tokens are shown when created; keep them out of source control and documentation. Author credentials can contribute drafts. The owner reviews and verifies content before readers can see it. Updates reject stale revisions instead of silently replacing a newer edit.

For remote readers, run on a controlled host behind HTTPS and an access-controlled network. A reverse-proxied instance **must** use `--require-auth`; otherwise a loopback proxy would inherit local-owner access:

```sh
python3 -m keystone serve --data /absolute/path/to/private-data \
  --host 127.0.0.1 --port 4318 --require-auth \
  --public-host knowledge.example.com
```

Replace the illustrative hostname with your actual hostname, preserve the incoming Host header through the proxy, and keep the application port private. If using direct private-network binding, specify the bind address and the exact hostname including port with `--public-host`. This is a lightweight application, not a managed identity platform; see [deployment and storage](docs/deployment.md) for the current boundaries.

## Back up, recover, and export

Choose local storage or a preconfigured rclone remote in setup or the owner's storage settings. For cloud backup, install rclone and configure the desired provider separately. Use an rclone crypt remote when client-side encryption is required; the local snapshot itself is not encrypted.

```sh
python3 scripts/backup.py --data ./data
python3 scripts/restore.py /path/to/keystone-snapshot.zip --to /path/to/empty-recovered-vault
```

Backups contain vault files and a checksum manifest. They do not contain installation settings or access tokens. Restore verifies the manifest and requires a new or empty destination. It restores a **vault folder**, not a fully configured installation. Follow the [recovery procedure](docs/deployment.md#recovery-test) to start a recovered library. Cloud backup is not live synchronization between multiple writers.

An optional static website can be generated from verified documentation:

```sh
python3 scripts/export_reader.py --data ./data --out ./exports/reader
```

The export is unencrypted and has no application login. Host it only where the audience is authorized to read every included document. **Do not publish private documentation to public GitHub Pages.** The toolkit source may be public while the runtime library stays private.

## Plan repeatable work

The example workflow demonstrates evidence review, draft capture, and verification:

```sh
python3 -m keystone workflow-plan --data ./data --id first-capture
```

A workflow references source documents, declares dependencies, and marks approval checkpoints. The planner checks missing sources, missing dependencies, and cycles. It returns an ordered plan with source revisions. **It does not execute the tasks.** The orchestration skill guides an assistant through separately authorized work with evidence and stop conditions.

## Develop and contribute

Run from the source checkout:

```sh
python3 -m unittest discover -s tests -v
```

See [validation notes](docs/validation.md) for the checks performed on this first version and the boundaries that still require your environment.

The GitHub Actions workflow runs the test suite across Linux, macOS, and Windows. It does not deploy a library or upload private vault contents. Keep implementation changes separate from private data, use the seed vault for non-sensitive examples, and document behavior changes in the relevant guide. See [architecture and roadmap](docs/architecture.md) for extension points and current limitations.

Released under the [MIT license](LICENSE).
