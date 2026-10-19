# Validation history

Latest source validation: October 18, 2026, on macOS. Historical release checks below retain their original scope. This record distinguishes automated tests, live local checks, and integrations that still need environment-specific validation.

## Session inbox, local meaning search, and workspace recovery (0.13.0)

On October 18, 2026, the source passed **232 Python tests, 62 JavaScript helper tests, and 6 native Swift tests**. New checks cover archive completeness, credential/approval exclusions, checksum corruption, unsafe paths, empty-target protection, reviewed repository remapping, disabled restoration automation, source-cited session proposals, update/combine behavior, repeated saves, stale revisions, duplicate suggestions, privacy guards, and local-owner/workspace-bound HTTP access.

Embedding tests use deterministic test vectors to verify actual cosine ranking of queries without shared document keywords, incremental refresh, model-digest invalidation, archived-source removal, recall excerpts, and fixed-loopback transport with redirect rejection. They are not a quality benchmark of an installed model. The real local Ollama service was reachable but had no supported embedding model; the browser showed the missing-model error. No model was downloaded, and meaning search remains off in the user's workspace.

Cross-platform CI exposed a Windows default-encoding error in UTF-8 inbox reads and a concurrent configuration-read race. The release uses explicit UTF-8 for private records, serializes configuration reads with in-process writers, and includes a Unicode evidence/review/save round-trip regression.

An isolated browser workspace verified collection without library writes, explicit handoff preparation, simulated assistant JSON import, body preview, reviewed update saved once, resume after reload, and full archive inspection/restoration into a separate inactive directory. Test notes and screenshots are synthetic. The native manager's new entries compile and its six lifecycle/API tests pass; a separate native-window visual pass is not claimed. The self-contained Apple Silicon package also passed all six Swift lifecycle tests, CLI/MCP forwarding, ad-hoc signature verification, and DMG integrity checks. Its bundled web files match final source.

## Open relationship network (0.12.2)

All **62 JavaScript tests** passed after removing anatomical paths, hemisphere constraints, and the layout picker. The bounded deterministic layout checks now cover an open network and centered single-node view. An isolated browser check confirmed the absence of anatomical paths, clear spacing, retained node selection, default type colors, and functioning project colors. Screenshots use synthetic documentation.

The Apple Silicon package was rebuilt. All **6 packaged Swift tests**, CLI/MCP forwarding, signature and DMG verification passed; bundled graph assets matched source. The existing local service was restarted on the same workspace. Note storage, graph relationships, and privacy behavior are unchanged.

## Project color toggle (0.12.1)

All **62 JavaScript tests** passed, including default type colors, shared and unassigned states, consistent project membership colors across different kinds, and stable colors when filtering. An isolated browser check verified the initial off state, changing orb colors and the legend, unchanged node positions and zoom, and restoration of the original type colors. The screenshot uses synthetic documentation. No note data or Obsidian settings were changed.

The updated Apple Silicon app was built; all **6 Swift tests** against its packaged runtime and CLI/MCP forwarding checks passed. Signature and DMG verification passed, and packaged graph assets matched the source. The native integration remains the same embedded local web route. This is a presentation-only change; Python behavior is unchanged from the 216-test 0.12.0 baseline. Cross-platform regression coverage runs in GitHub CI.

## Knowledge brain (0.12.0)

The source passed **216 Python tests and 60 JavaScript tests** on macOS. Added coverage exercises explicit graph relationships, unambiguous link resolution, source/workflow/skill edges, hidden-note and local-metadata boundaries, node filtering, deterministic bounded layout, colors and size caps, and embedded-view credential cleanup. The graph tests also reject code/comment link examples. Existing authentication semantics remain unchanged.

An isolated browser workspace with synthetic notes verified the brain layout, orb selection, recorded relationships, type and neighborhood filters, zoom/reset, and opening documentation. The embedded route preserved its presentation option across local authentication, hid duplicate browser navigation, and returned from project notes to the brain. Screenshots use demonstration data, not the user's private notes. No AI inference or workflow execution was involved.

The Apple Silicon 0.12.0 app compiled and the packaged runtime passed all **6 Swift lifecycle/API tests**, CLI forwarding, and MCP initialization/tool discovery. App signature and DMG integrity verification passed; bundled HTML, JavaScript, and CSS matched current source. Native WebKit code was compiled and its embedded web route tested in the browser; a separate native-window visual pass was not performed for this release. The app remains ad-hoc signed and unnotarized. Windows/Linux and older macOS packaged artifacts were not exercised locally.

The existing local service was upgraded on the same workspace and retained its 13 notes. Its authenticated graph returned 14 nodes and 46 recorded relationships. The graph did not modify notes, enable repository capture, or change sharing settings.

## Focused workspace (0.8.1)

The 48 JavaScript tests passed, including role-scoped grouped navigation and non-mutating duplicate-title rendering. The native SwiftUI target compiled and the Apple Silicon package was rebuilt. Browser checks exercised search and type filtering, full-page reading, returning to retained results with Escape, Focus mode enter/exit, optional capture fields, and a 390px-wide navigation layout without horizontal overflow. The native UI showed the simplified dashboard and expandable service controls against the existing workspace. No note edits were saved during these UI checks.

The underlying Python APIs, storage, and assistant connection contracts are unchanged. The existing platform suites and native API harness continue in CI. Signing and platform limitations from 0.8.0 still apply.

## Native SwiftUI manager (0.8.0)

On October 18, 2026, the source passed **175 Python tests, 46 JavaScript tests, and 6 Swift tests**. The Swift suite exercised the real source server and the packaged runtime separately with disposable workspaces: create/update/select, retained backups, stale-workspace rejection, and service shutdown. The bundled executable forwarded both CLI and MCP initialization/tool discovery successfully. No private vault was modified in these lifecycle checks.

The Apple Silicon app was built using Xcode 26.5 / Swift 6.3.2 and Python 3.14.6. The full app signature and DMG verification passed. Native UI inspection confirmed detection/adoption of the existing local installation and rendered workspace settings, backup history, and assistant connection status. The manager remembers that installation without copying files or retargeting assistants. Final UI screenshots are local deliverables, not repository fixtures containing user paths.

The declared macOS minimum is 13; only macOS 26.5 Apple Silicon was exercised locally. The app remains ad-hoc signed and unnotarized. Intel Macs, older macOS, packaged Windows/Linux artifacts, cloud uploads, and new assistant account enrollment were not validated for this change. Windows/Linux still use their existing browser launchers. The added macOS CI job runs the native live-service harness; the existing nine Python/browser platform jobs remain.

## First-visit guide and skill matching (0.7.1)

The complete source passed **173 Python tests and 46 JavaScript tests**. First-visit checks cover fresh and returning browser state, explicit destinations, clearing the preference, and blocked storage. Existing skill matching checks cover exact names, keyword overlap, saved-build provenance and freshness, stale suggestions, bounded output, access boundaries, and safe UI rendering.

A disposable local instance opened Getting started on its first root visit, then the Library on a second root visit in the same browser. Direct page links are preserved. The preference is local to the browser profile and origin, not an engineer account or vault setting. Clearing site data resets it; blocked storage may show the guide again on a new page session. Getting started remains available explicitly. Guide rendering was also checked for owner, author, reader, static-reader, and signed-out roles; authoring and setup links follow their existing access boundaries.

The live source portal includes the Getting started guide, copyable capture/handoff prompts, suggestion explanations, and existing-skill checks. Matches use metadata and saved-build provenance, not semantic AI analysis. No user notes or installed skills are modified by matching.

The 0.7.1 Apple Silicon app, ZIP, and DMG were rebuilt on October 18, 2026. The app signature and disk-image checksum verification passed. The bundled CLI initialized a disposable vault and returned skill suggestions. Packaged HTML, JavaScript, CSS, and brand assets matched the source bytes, and the app metadata reported 0.7.1. The app remains ad-hoc signed, not Apple Developer ID signed or notarized. Intel Mac, Windows, Linux desktop artifacts, and fresh cloud-account integrations were not exercised for this patch.

## AI workflow handoff and existing skills (0.7)

The full suite passed **169 Python tests and 43 JavaScript tests**. New checks cover explicit cross-document source packs, proposal shape and citations, dependency cycles/missing references, preview acceptance revisions, source changes, parent/child skill generation, private storage path limits, bounded manifest discovery, folded metadata, duplicate locations, read-only preservation, and local-owner versus shared-author/reader access. The affected analysis suite passed again after the final package formatting change. The updated bundled build-skill and all four generated parent/child test packages passed the skill-creator validator.

In a disposable browser workspace, two synthetic cache procedures were selected and a source-complete handoff was prepared. An assistant-authored test proposal combined them into readiness, rebuild, and verification skills. The browser preview displayed source citations, dependencies, an approval checkpoint, and missing environment inputs. Accepting added four AI suggestions (one complete workflow and three child skills); the complete package was previewed and saved. This exercised local handoff/import/build behavior, not a round trip through a separate ChatGPT or Claude account, and did not execute the generated procedures.

Read-only browser discovery found an existing non-Mnemos skill in both personal Codex and Claude folders. The actual portal was restarted on its existing data directory and showed the new controls. User source notes, assistant skills, and the separate tunnel were not modified. The Apple Silicon 0.7 app and DMG were rebuilt; the bundled CLI prepared a handoff, previewed and accepted a fixture proposal, and discovered its whole-workflow and child candidates. The build remains ad-hoc signed and not notarized. Windows/Linux packages were not exercised locally.

## Available skills (0.6)

The complete source passed **159 Python tests and 41 JavaScript tests**. New checks cover procedural discovery, examples/draft/archive distinctions, exact source copies, preview/save revision conflicts, external source edits during generation, immutable build history, source freshness, dependency ordering and approval checkpoints, secret-pattern refusal, size and path limits, CLI export, reader/author boundaries, cross-origin and stale-workspace rejection, and escaped UI output. The two generated target packages and the updated bundled build-skill instructions passed the official skill-creator validator; validation used an isolated development dependency and did not add a runtime requirement.

In a separate browser test workspace, a synthetic runbook was selected, previewed for Claude, saved, and downloaded as a three-file ZIP whose contents were inspected. Editing its source then showed “Sources changed — rebuild recommended.” The ChatGPT preview showed local installation and portable cloud handoff guidance. No package was uploaded or installed into an assistant account, and no operational execution of a generated skill is claimed.

The user's source portal was restarted on the same workspace and displayed two suggestions from existing notes. No user notes were changed or skills automatically saved. The separate tunnel was left running. The midnight/violet/cyan identity appears in the portal and setup page; the duplicate legacy favicon was removed.

The Apple Silicon 0.6 app and DMG were built. Its bundled CLI successfully initialized an isolated workspace, discovered suggestions, previewed and saved a skill, and exported the ZIP. The app version and packaged icon matched the release assets. It remains ad-hoc signed, not notarized; Windows/Linux builds were not exercised locally.

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

The 0.7.0 prompt recovered all 110 application files at `4f23f0a16bbfbd3a11bf1e007ee9a66b02181f28`. Independent comparisons matched every byte and executable mode. The utility extracted from the finished prompt rejected corruption, truncation, traversal, and an existing destination. Private runtime records and reconstruction prompts are excluded from the capsule.

The 0.6.0 prompt recovered all 107 application files at `3e00262c79091496dba57e1d4f2ac5736da9d44a`. Independent comparisons matched every byte and executable mode; the utility extracted from the finished prompt passed corruption, truncation, traversal, and existing-destination rejection checks. The capsule excludes private data and all reconstruction prompts.

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

## Project systems (0.9.0)

Adds top-level project definitions, shared repository membership, project-scoped search/recall/handoffs/skills, Flow notes, explicit system-explanation handoffs, evidence-change checks, and non-overwriting Obsidian map generation. New tests cover legacy note association without byte changes, stable IDs on rename, missing checkout registrations, scoped retrieval and skills, explanation/code provenance, exclusion of unrelated notes and local checkout paths, source freshness after commits, map/backup contents, reader visibility, and management endpoint guards. The browser round trip was checked in an isolated three-repository demo; no real notes or project registrations were added.

Validation on Apple Silicon macOS: 183 Python tests, 51 JavaScript tests, and 6 Swift tests passed. The packaged native executable passed its isolated live-service lifecycle and MCP discovery checks. All five bundled skills passed the skill validator. Packaged web and skill files match the source bytes; the ad-hoc app signature and DMG checksum verified. These results do not establish operational correctness of user-generated skills or AI explanations.

## 0.10 privacy and local authentication

199 Python tests, 53 browser-helper tests, and six native Swift tests pass locally. Security tests cover default denial; separate AI/team audiences; transitive and shared-repository restrictions; stale/revoked approvals; new captured commits; blocked immutable skill downloads; credential scanning; static readers; unknown attachments; cloud backup denial; local login, cookie flags, Host/Origin guards, and owner-token management denial. Tests use isolated synthetic workspaces.

Browser verification exercised the three-policy project editor and explicit note approval. No real project or note was approved for sharing during verification. The package remains ad-hoc signed and unnotarized.

## Git remote documentation backup (0.11.0)

The regression suite now contains 210 Python tests and 55 browser-helper tests; all pass, along with six native Swift tests. New tests cover isolated local Git commits, unchanged snapshots, private-history denial, failed transport preserving commits, modified remote detection, existing checkout protection, path validation, opt-in scheduling, three-color status, and local-owner/workspace API guards. Successful and failed remote transport responses are simulated in tests; no customer documentation is uploaded. Git host authentication and live remote availability must be verified in the user's environment.
