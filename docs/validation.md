# Version 0.1 validation

Validated on October 17, 2026, on macOS. This is a first working local release, not a claim of a production security certification.

## Automated checks

The Python suite passed 39 tests covering document storage, draft and reader boundaries, multiple authors and optimistic concurrency, basic Obsidian frontmatter, path protection, workflow ordering, authentication, origin checks, backup recovery, cloud failure retention, verified-only export, context budgets, source provenance, and project-scoped agent configuration.

The JavaScript helper suite passed 12 tests covering Markdown rendering and unsafe-link rejection, JSON and Markdown imports, draft enforcement, preservation of source references, dates, keyword relevance, and static recall budgets. Run it with `node --test tests/web.test.cjs`; Node is only needed for these development tests, not for running Keystone.

The MCP capture test exercises draft-only capture and subsequent recall. A separate skill exercise saved a searchable handoff that distinguished a source-reported successful test from a staging deployment that was proposed but not performed. It retained unknowns and removed the supplied credential placeholder.

The ChatGPT Actions schema parses as JSON, resolves its local schema references, and exposes only recall, document read, and draft capture with Bearer authentication. The fields and role constraints were checked against the application handlers.

## Live checks

- Installed Obsidian 1.14.4 through Homebrew after confirming that it was absent.
- Initialized a new dedicated vault and opened it in Obsidian.
- Saved a real implementation context draft through the browser and opened the same Markdown document in Obsidian.
- Used the web portal to retrieve source-linked context and inspect a dependency-ordered workflow handoff.
- Created a real local backup through the web portal and restored all 21 snapshot files into a separate directory with checksum verification.
- Built a static reader export containing seven verified example documents, excluding the private draft and access configuration.

## Verification boundaries

- Cloud backup command construction and failure handling were tested with mocks. No cloud credentials were supplied, so no live cloud upload was performed.
- Windows and Linux installers were implemented but not executed on those operating systems. The repository includes a cross-platform CI workflow; it has not yet run on GitHub.
- Browser save, read, recall, workflow, and backup flows were checked. The browser automation's file chooser did not return a selection event, so the file chooser itself has not been verified end to end. The importer is also available through the tested CLI.
- Project-local Codex and Claude Code configurations were generated. Activating them requires the client to reopen/trust the project. A live Claude or separate Codex client connection was not exercised.
- The prepared ChatGPT Actions adapter requires an HTTPS host and a configured credential. It has not been connected to a live custom GPT or tested end to end in ChatGPT.
- The local MCP service uses standard input/output. An authenticated remote MCP deployment for cloud chats is a future integration.
- Retrieval is keyword-based. Character budgets are enforced; token counts are estimates rather than tokenizer measurements.
- Snapshot hashes detect corruption; they are not authenticity signatures. Cloud encryption depends on the selected rclone remote. Local vault and ZIP files are unencrypted.
- Team reader hosting and a public source repository have not been deployed or created.
