# Version 0.5.1 validation

Validated on October 17, 2026, on macOS. This record distinguishes automated tests, live local checks, and integrations that still need environment-specific validation.

## Visual identity (0.5.1)

The midnight/violet/cyan identity and shared geometric icon were checked in the live portal and setup page. The existing core, backup/recall/export, and launcher suites passed 31 Python tests; all 39 JavaScript helper tests passed. No behavior-only tests were added for the visual changes. A portable reader smoke check confirmed the current version and identical SVG/PNG assets. The Apple Silicon app and DMG were rebuilt with the native ICNS; the packaged icon bytes matched the committed asset and the bundled workflow planner produced the example plan successfully. Windows ICO wiring is included but the Windows package was not built locally.

## Automatic project refresh (0.5)

The source passed **147 Python tests and 39 JavaScript tests**. Ten additional Git/service tests cover default-off and strict opt-in, initial/new-commit capture, unchanged-commit deduplication, preservation of human edits and open settings revisions, changed source selection, missing-folder disable, persistence across monitors, duplicate workers, active-workspace selection, stale-pointer/shared-server/stop guards, error isolation/retry, legacy registrations, and an actual running server detecting commits without refresh requests. HTTP authorization tests include the new automatic-refresh endpoint; UI helper tests verify accessible switches and escaped error text.

In the isolated browser workspace, automatic refresh was enabled for the synthetic Aurora service repository. A new fixture commit was captured without pressing Refresh. An open settings form retained its unsaved source selection, the per-project switch turned off, the form saved successfully after background capture, and Open context fetched the newly created draft with its exact commit and excerpt. Re-enabling captured the changed selection. The test server used a shortened interval; the shipped default remains 60 seconds. No real user repo was enabled automatically.

The 0.5 Apple Silicon standalone app and DMG were rebuilt. The bundled CLI initialized a disposable workspace, registered a synthetic checkout, and the bundled server captured its initial context automatically with a running 60-second worker. The bundled CLI then disabled the choice successfully. The app remains ad-hoc signed, not notarized; Windows/Linux packaged behavior is not locally validated.

## Projects (0.4)

The final source passed 137 Python tests and 38 JavaScript tests. Fourteen new Git tests exercised committed-only capture, unchanged working trees/indexes, source limits/exclusions and credential screening, snapshot history, preservation of human edits, latest-context recall and explicit historical handoff, revision conflicts, disconnect behavior, missing/empty/moving repositories, worktrees, disabled filesystem monitors, ignored replacement refs, and process/network environment restrictions. HTTP checks covered local-owner restrictions, origin checks, and stale-workspace rejection; JavaScript checks covered escaping project card data.

In an isolated browser workspace, a synthetic local checkout was registered, refreshed, and opened as a draft with its README excerpt and commit/blob evidence. Source-selection editing showed the changed-selection state; another refresh created a separate snapshot. The page was inspected at desktop and 560-pixel widths without horizontal content overflow. The user's actual local portal was restarted on its existing workspace and the empty Projects screen opened; no real user repository was registered automatically and the separate tunnel was not stopped.

The 0.4 Apple Silicon desktop bundle was rebuilt and smoke-tested with an isolated workspace: bundled CLI initialization, project registration, committed-source refresh, and inventory succeeded. It remains ad-hoc signed, not notarized. Windows/Linux packaged behavior remains untested locally. Manual refresh does not inspect uncommitted work or automatically explain code changes; screening is not comprehensive secret detection.

## Standalone reconstruction prompt

The 0.5.0 prompt recovered 99 application files at `2a5f3a40f0f0792c1a9beed2614410cdb77416db`, excluding the reconstruction-prompt directory to prevent recursive payload growth. Independent comparisons verified every byte and executable mode. Its extracted utility passed corruption, truncation, traversal, and existing-destination rejection checks. The user's source portal was restarted on the same active workspace; the 60-second monitor was running and no user repositories were registered or enabled.

The 0.4.0 reconstruction prompt recovered all 98 files at commit `c730eaaed4e256ccf15df61de842b55565f87849`, with byte and permission comparisons against Git. Its independently extracted utility passed corruption, truncation, traversal, and existing-destination rejection checks. The source is the same baseline validated above; the older 0.3.0 prompt remains frozen.


The [reconstruction prompt](../prompts/rebuild-mnemos-v0.3.0.md) embeds all 94 tracked source files from commit `38598d2ac1d1b02f179c957805db55cce9d8fd48`. Recovery into a fresh directory reproduced every file byte and POSIX executable mode. The recovery utility was extracted from the finished prompt and executed independently. Checks confirmed rejection of a truncated payload, archive corruption, a traversal path even with a recomputed archive checksum, and an existing destination without changing its contents. The recovered application passed all 122 Python tests and 37 JavaScript tests. This verifies source recovery and those automated checks; it does not claim that every ChatGPT environment can execute attachments or that desktop binaries built elsewhere will be byte-identical.

## Automated checks

The Python suite passed 122 tests covering document storage, draft and reader boundaries, multiple authors and optimistic concurrency, basic Obsidian frontmatter, path protection, workflow ordering, authentication, origin checks, backup recovery, cloud failure retention, verified-only export, context budgets, source provenance, project-scoped agent configuration, Claude Desktop configuration preservation, and private ChatGPT tunnel setup and credential handling.

The JavaScript helper suite passed 37 tests covering Markdown rendering and unsafe-link rejection, JSON and Markdown imports, draft enforcement, preservation of source references, dates, keyword relevance, static recall budgets, setup flows, and stale-workspace recovery. Run it with `node --test tests/web.test.cjs`; Node is only needed for these development tests, not for running Mnemos.

The added checks cover fresh browser setup, isolated storage validation, custom-location persistence, preservation of documents and tokens, local-owner-only setup, Windows command quoting, source selection, bounded context packs, skill archive contents, skills-only installs, legacy connection compatibility, generated Obsidian links, and safe new-draft import even from an existing editor. All five skills passed the skill-creator validator.

Workspace lifecycle checks cover explicit update/create/select modes, default persistence across restart and configuration edits, read-only inspection, preservation of selected workspace settings, stale browser saves and downloads, stale configuration previews, activation failure, competing servers, in-flight writes, and default CLI/MCP resolution. Existing explicitly pinned assistant and tunnel connections remain on their configured paths.

The MCP capture test exercises draft-only capture and subsequent recall. A separate skill exercise saved a searchable handoff that distinguished a source-reported successful test from a staging deployment that was proposed but not performed. It retained unknowns and removed the supplied credential placeholder.

The ChatGPT Actions schema parses as JSON, resolves its local schema references, and exposes only recall, document read, and draft capture with Bearer authentication. The fields and role constraints were checked against the application handlers.

## Desktop and connection checks

Version 0.3 adds tests for connection inventory, pinned-workspace mismatches, credential omission, malformed/disabled/missing configurations, refusal to execute arbitrary configured commands, read-only MCP tool discovery, tunnel health interpretation, cache invalidation, bundled command dispatch, external writable data locations, same-instance reuse, and local-owner/workspace/origin protections around stop controls.

The standalone Apple Silicon Mac app was built with Python 3.14.6 and PyInstaller 6.16.0 on macOS 26.5. An isolated bundled CLI initialized a test vault; bundled stdio exposed capture, recall, search, read, and workflow tools. A detached bundled launch started successfully (first startup took approximately 36 seconds), its dashboard API responded, a second launch reused the same workspace instance, and its stop endpoint completed. The source launcher also reopened the existing library in the background. Browser checks exercised local Codex discovery and the existing tunnel health check without requesting credentials or changing connections.

The Mac app uses ad-hoc signing, not Developer ID/notarization. Windows and Linux build automation is included but those packaged artifacts have not been run locally. Test status proves the stated local check only; assistant/cloud account access is not inferred.

## Live checks

For version 0.2, the local browser completed all four setup steps in an isolated test installation, selected cloud file handoff, and opened the resulting library. The source picker started with no selection. A downloaded JSON pack contained exactly the selected source with its full text and revision. The existing ChatGPT app display name was changed to Mnemos. Claude Desktop’s equivalent legacy connection was renamed with a backup and a real stdio tool-discovery preflight; Claude was not restarted during the rename. The repository directory and tunnel identity remain unchanged to preserve configured paths.

The repeatable setup flow was also checked in an isolated browser installation: create a new default through all four steps, inspect and activate a second existing workspace, and verify that both previous libraries retain their own settings and notes. A draft open in an older tab was rejected after activation; reloading opened the active library while retaining a downloadable copy of the draft. Independent file checks confirmed that the rejected draft was not saved into either workspace. The configured-workspace overview was inspected at desktop and narrow-panel sizes. The user's running portal was refreshed without switching its workspace or changing its assistant connections.

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
