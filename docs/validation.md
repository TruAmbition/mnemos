# Version 0.2 validation

Validated on October 17, 2026, on macOS. This record distinguishes automated tests, live local checks, and integrations that still need environment-specific validation.

## Automated checks

The Python suite passed 88 tests covering document storage, draft and reader boundaries, multiple authors and optimistic concurrency, basic Obsidian frontmatter, path protection, workflow ordering, authentication, origin checks, backup recovery, cloud failure retention, verified-only export, context budgets, source provenance, project-scoped agent configuration, Claude Desktop configuration preservation, and private ChatGPT tunnel setup and credential handling.

The JavaScript helper suite passed 24 tests covering Markdown rendering and unsafe-link rejection, JSON and Markdown imports, draft enforcement, preservation of source references, dates, keyword relevance, and static recall budgets. Run it with `node --test tests/web.test.cjs`; Node is only needed for these development tests, not for running Mnemos.

The added checks cover fresh browser setup, isolated storage validation, custom-location persistence, preservation of documents and tokens, local-owner-only setup, Windows command quoting, source selection, bounded context packs, skill archive contents, skills-only installs, legacy connection compatibility, generated Obsidian links, and safe new-draft import even from an existing editor. All five skills passed the skill-creator validator.

The MCP capture test exercises draft-only capture and subsequent recall. A separate skill exercise saved a searchable handoff that distinguished a source-reported successful test from a staging deployment that was proposed but not performed. It retained unknowns and removed the supplied credential placeholder.

The ChatGPT Actions schema parses as JSON, resolves its local schema references, and exposes only recall, document read, and draft capture with Bearer authentication. The fields and role constraints were checked against the application handlers.

## Live checks

For version 0.2, the local browser completed all four setup steps in an isolated test installation, selected cloud file handoff, and opened the resulting library. The source picker started with no selection. A downloaded JSON pack contained exactly the selected source with its full text and revision. The existing ChatGPT app display name was changed to Mnemos. Claude Desktop’s equivalent legacy connection was renamed with a backup and a real stdio tool-discovery preflight; Claude was not restarted during the rename. The repository directory and tunnel identity remain unchanged to preserve configured paths.

The following underlying installation and connection checks were completed during version 0.1, before the rename:

- Installed Obsidian 1.14.4 through Homebrew after confirming that it was absent.
- Initialized a new dedicated vault and opened it in Obsidian.
- Saved a real implementation context draft through the browser and opened the same Markdown document in Obsidian.
- Used the web portal to retrieve source-linked context and inspect a dependency-ordered workflow handoff.
- Created a real local backup through the web portal and restored all 21 snapshot files into a separate directory with checksum verification.
- Built a static reader export containing seven verified example documents, excluding the private draft and access configuration.
- Installed the local connector in Claude Desktop 2.42304.0 while preserving and backing up its existing settings. Restarted the app and confirmed the connector was enabled.
- Successfully called recall, search, and document read from a real Claude Desktop chat. The same chat saved a new draft context, which was independently verified in the vault.
- Created an approved private OpenAI tunnel associated with the user's selected account/workspace and prepared its isolated local profile. The official tunnel-client release checksum was verified. After the user enabled the launching app's Documents access and supplied the runtime credential through hidden input, the local health and readiness checks both passed.
- Connected the toolkit under its original Keystone name as a private ChatGPT plugin. A real ChatGPT chat recalled six source documents and read the two project-specific notes. The same chat searched for, saved, and read back a new draft context; its title, status, content, and chat source URL were independently verified in the vault.
- One ChatGPT document read initially failed with an MCP initialization error; a sequential retry succeeded. The subsequent search, capture, and read-back test also succeeded sequentially. The transient failure's cause is unconfirmed, so these checks do not establish error-free operation under concurrent hosted requests.

## Verification boundaries

- Cloud backup command construction and failure handling were tested with mocks. No cloud credentials were supplied, so no live cloud upload was performed.
- Windows quoting and backup-path behavior were unit-tested with platform fixtures. Windows and Linux installers were implemented but not executed on those operating systems. The repository includes a cross-platform CI workflow; it has not yet run on GitHub.
- Browser save, read, recall, workflow, and backup flows were checked. The browser automation's file chooser did not return a selection event, so the file chooser itself has not been verified end to end. The new paste-import and file-import handlers were exercised by automated tests, including new-draft isolation and preview without saving. A fresh browser tab rendered the paste interface, but the browser automation stalled around file-selection/default interactions, so a complete live import round trip is not claimed. The importer is also available through the tested CLI.
- Project-local Codex and Claude Code configurations were generated. Activating them requires those clients to reopen/trust the project. The separate Claude Desktop connection was exercised live; Claude Code and a separate Codex client have not been exercised.
- The prepared ChatGPT Actions adapter requires an HTTPS host and a configured credential. It has not been connected to a live custom GPT or tested end to end in ChatGPT.
- The local MCP service uses standard input/output. The ChatGPT Secure MCP Tunnel route was exercised live and requires the local computer and tunnel process to remain running. A public authenticated remote MCP deployment for browser-based Claude remains a future integration.
- Retrieval is keyword-based. Character budgets are enforced; token counts are estimates rather than tokenizer measurements.
- Snapshot hashes detect corruption; they are not authenticity signatures. Cloud encryption depends on the selected rclone remote. Local vault and ZIP files are unencrypted.
- Team reader hosting and a public source repository have not been deployed or created.
