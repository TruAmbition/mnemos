# Architecture and roadmap

## One knowledge library, several interfaces

```text
Accessible engineering work
          │
          ▼
Assistant skills ── local MCP or CLI ──► Dedicated Markdown vault
          ▲                                     │
          │                              ┌──────┴──────┐
   bounded context                       ▼             ▼
   with source revisions              Obsidian      Web library
                                                readers / authors
                                                     │
                                         local or cloud snapshots
```

Markdown files are the durable source of truth. The application reads them directly; there is no separate database that must be synchronized to make a saved document searchable. Templates are excluded from search. Workflow JSON references stable document IDs rather than depending on a human-readable title remaining unchanged.

The assistant and application have separate jobs. An assistant interprets accessible work, drafts useful knowledge, and reasons about plans. Mnemos validates structured captures, saves documents, retrieves matching sources, and produces dependency plans. The application does not contain a model inference engine.

## Distribution and private state

The source repository contains application code, web assets, example notes, templates, skills, and tests. Each user creates a separate runtime directory:

```text
private-data/
  config.json          Owner, backup settings, hashed access credentials
  vault/               Obsidian Markdown and workflow files
  backups/             Default local snapshot destination
  backup-history.json  Backup outcomes, when backups have run
  skill-builds/        Immutable generated skill snapshots (private, outside the vault)
  skill-analysis/      Explicit source handoffs for external AI reasoning
  skill-proposals/     Reviewed, accepted workflow decompositions
```

The vault is always `vault/` under the selected data directory. Initialization refuses to adopt a nonempty unconfigured vault and does not merge with another Obsidian library. Opening the dedicated folder in Obsidian keeps its vault configuration separate. Choosing a data directory outside existing vaults is part of setup.

## Knowledge model

New documents use stable IDs in their filenames. Every document carries an ID, title, type, status, project, tags, author, timestamps, and summary. Optional `sources` and `related_ids` preserve provenance and links. When a related ID resolves to an existing document, saving adds a managed Related knowledge section with an Obsidian link to that source. Unresolved IDs stay metadata; the system does not fabricate target notes. Obsidian backlinks and its graph can use the resulting links. A content revision is derived from the saved file and used to detect stale updates. `example: true` identifies illustrative seed content and remains visible to readers.

The common types serve different purposes:

| Type | Purpose |
| --- | --- |
| `runbook` | Repeatable steps, expected results, verification, recovery |
| `knowledge` | Reusable explanation, use cases, boundaries |
| `troubleshooting` | Symptoms, diagnostic branches, evidence, resolution |
| `decision` | Context, alternatives, rationale, consequences |
| `work-log` | What occurred and what evidence supports it |
| `microtask` | One bounded action with inputs, outputs, and stop conditions |
| `context` | Compact task state for continuation across assistants |

Captures are drafts until the owner verifies their stated scope. Reader credentials expose verified documents. An author identity comes from the configured owner or authenticated session, not an arbitrary payload field. Verification is a human/process claim: the application cannot prove a command was run simply because status is set to verified.

The frontmatter reader supports the basic scalar and list forms used by these templates; it is not a general YAML implementation. Use one-line JSON-compatible scalar or array values for portable metadata. Arbitrary Obsidian plugin features and embedded HTML are not required to read the documents.

## Search and context recall

Keyword search matches titles, body text, summaries, projects, and tags. Recall creates a bounded bundle of source excerpts with document IDs, revisions, status, and example labels. It does not invent an answer or retrieve unseen chat history. Its character budget controls output size; token counts are estimates rather than tokenizer measurements.

Local MCP exposes search, document reads, draft capture, recall, and workflow planning. It starts as a subprocess of a compatible assistant client. The MCP process uses local filesystem access and has author-level capture behavior. It is not the HTTP reader server and is not a remotely authenticated cloud connector. A separate [ChatGPT Actions schema](cloud-chatgpt.md) exposes a limited set of existing HTTP operations after the user hosts HTTPS and configures a dedicated credential; it is prepared integration material, not an automatically deployed connection.

## Guided setup and portable handoff

One saved selection at the checkout's `data/installation.json` defines the active default. Omitted `--data` arguments in the CLI, backup/export helpers, and new assistant installers use that selection. Explicit paths and previously installed assistant connections remain pinned; switching defaults does not move notes or retarget connected clients. A default-following MCP process closes before handling a request after the selection changes, requiring a restart; pinned MCP processes continue with their authorized workspace.

The launcher serves local `/setup.html` for choosing the author, dedicated data folder, backup destination, Obsidian setup, and assistant mode. It reports actual local readiness separately from any external connection status. It does not automatically install credentials or connect cloud accounts.

Cloud handoff exports bounded recall excerpts and source metadata. Full source bodies are optional and explicitly selected, with a separate size limit. The user chooses what to upload. The `mnemos-handoff` skill turns those supplied sources and accessible task evidence into a single new draft capture JSON. Portal import previews it and creates a new draft; it does not overwrite an existing document. Source-only skill export needs no initialized vault and never packages private runtime data.

Neither the local MCP route nor the file handoff needs a tunnel. Optional existing tunnel and hosted Action integrations remain separate. A skill installed in a cloud environment does not confer access to the user's Mac.

## Suggested and generated skills

`mnemos/skill_builder.py` selects active procedural documents and valid dependency plans locally. It packages a small SKILL.md with full source references and revision provenance; no model inference or executable generation is involved. Owner/author API routes support discovery, preview, save, history, ZIP download, and Markdown handoff. Readers and static exports do not expose these private builds. Preview and save check source revisions and the selected name, description, and target. Saved JSON snapshots live under `skill-builds/`; the vault-only backup does not include them. See [Available skills](available-skills.md).

`skill_analysis.py` prepares bounded, explicit source handoffs and validates imported proposals before acceptance. It adds whole-workflow and child candidates, validates source revisions and dependency graphs, and never invokes a model or executes generated steps. `skill_inventory.py` reads bounded local manifest metadata; its HTTP route is restricted to the local owner. Neither inventory discovery nor an accepted AI proposal grants execution authority.

The existing five MCP tools are unchanged. Local agents can use the skill-builder CLI; a remote chat must use supplied files or an appropriately connected tool and cannot assume access to this workstation.

## Name compatibility

Mnemos is the canonical package and product name. `python -m keystone` remains an alias, and the existing checkout directory is deliberately not renamed. Stable backup manifest names, storage lock names, and tunnel profile identities remain compatible. Matching legacy project MCP entries are reused; the Claude Desktop installer can rename an equivalent entry only on explicit apply with backup.

## Collaboration and trust

The first deployment supports one owner with reader credentials. Named author credentials allow additional contributors without changing the document format. Roles apply to the library as a whole. There are no per-project access policies, enterprise single sign-on, review queues, or tamper-evident audit guarantees in this version.

Updates check a supplied source revision, cross-process storage locks serialize Mnemos writers, and writes use temporary files and replacement to reduce partial writes. These controls are not a distributed transaction system. Run one shared application instance per data directory and avoid simultaneous edits to the same file from Obsidian, independent scripts, or sync software. Treat backups as recovery points; the application is not a full revision-history browser.

## From documentation to agentic workflows

A workflow is a directed acyclic graph of steps. Each step references a source document, declares dependencies, and may require an approval checkpoint. Planning validates the graph and resolves current source content. It returns a plan only.

The orchestration skill adds execution discipline to an assistant that has suitable tools: check sources, validate prerequisites, execute only authorized work, record evidence, and stop dependents on failure. The skill-building workflow captures verified knowledge as a portable skill with source revisions and refresh rules. Neither workflow grants blanket permission to run commands found in a note.

## Roadmap

These are future extensions, not features claimed by this release:

1. **Broader cloud account integration.** A managed authenticated remote MCP transport, per-user identity and authorization, and client-specific end-to-end tests. Local MCP, portable file handoff, optional tunnel helpers, and the hosted Action schema already provide distinct connection choices. No route implies automatic access to all chat history.
2. **Hosted semantic providers.** Local meaning-based retrieval is available through optional Ollama embeddings in 0.13.0. Hosted providers remain future work.
3. **Stronger collaboration.** Review requests, durable change history, fine-grained permissions, and audit events suitable for a larger team.
4. **Managed operations.** Scheduled snapshots, retention policies, automated recovery drills, service packaging, and storage-provider setup assistance.
5. **Controlled execution.** A separately scoped runner with typed task inputs, bounded retries, approvals, isolated execution, checkpoints, and documented rollback. The plan format provides a starting point, not an existing execution engine.

Keep these additions optional so the core library stays readable in Obsidian and portable as ordinary files.


## Registered Git projects (0.5)

`mnemos/projects.py` stores explicit local registrations in private config and uses bounded, read-only Git commands to inspect committed HEAD. Selected regular text blobs become new draft context notes, linked to previous snapshots. Exact commits and blob IDs provide provenance; generated snapshots make no semantic claims about architecture or rationale. Registrations preserve source/exclusion settings and optimistic revisions. HTTP management is local-owner-only and uses existing workspace guards. No remote fetch or repository code execution is performed.

Ordinary recall and bounded handoff prefer the registered latest snapshot. Library search and explicit handoff selection retain history. Config/notes are separate atomic files; failures can leave an unreferenced draft but never require overwriting repository content or existing notes. See [project management](projects.md) for limits and portability.

`mnemos/project_monitor.py` adds a local-service worker with persistent per-registration `auto_refresh` opt-in (default false), a 60-second interval, immediate wake on portal changes, and in-memory check/error status. The worker starts only for the local setup-enabled server and stops with it. It uses the same workspace → installation-pointer → data-lock order as browser writes. Opt-in and the latest commit/selection fingerprint are checked under the writer lock; duplicate monitors cannot create repeated snapshots for an unchanged fingerprint. Settings revisions exclude successful-capture metadata so background writes do not invalidate open settings forms. Error isolation permits later repos to run. No scheduled OS job or remote Git operation is installed.

## Knowledge brain (0.12)

`graph.py` assembles nodes and edges from visible note links, project memberships, declared repository relationships, workflows, and (local owner only) saved skill builds. `/api/graph` uses the current session audience and role. Static readers build from their exported documentation only. `brain.js` provides a dependency-free SVG renderer with bounded layout and a 500-node filtered viewport. It makes no model calls or storage changes. The native manager embeds that authenticated loopback route in an ephemeral WebKit view. See [Knowledge brain](knowledge-brain.md) for interaction, scope, and Obsidian differences.


## Local workspace tools (0.13.0)

`session_inbox.py` stores bounded evidence and proposals under `session-inbox/`. The local-owner API/CLI collects selected current document versions plus supplied text; it does not scrape chats or read uncommitted work. Preparing a handoff checks current source fingerprints and AI approval, screens for credentials, and requires confirmation for supplied context. Review normalizes 1–12 source-cited create/update/combine items, shows duplicate title matches and body diffs, and binds saves to the exact proposal digest. Items save individually as drafts, with stable generated IDs, source revisions, and repeat-save protection. Updates use the existing note revision; combine preserves originals. A process failure during an update can require manual reconciliation; this is not a multi-note transaction system.

`semantic.py` optionally connects directly to `127.0.0.1:11434` through Python's HTTP client, without proxies or redirect following. Three supported local embedding model names are allowlisted. Model identity/digest and note revisions invalidate cached vectors. Passages overlap by 200 characters, use 2,400-character windows, and rank by cosine similarity with a small keyword boost. Recall includes the matched passage. Search applies current local-owner/project/type/archive scope and prefers latest repository snapshots. The index contains vectors and IDs, stays outside the vault, and is omitted from backups; turning the feature off removes it. Search refreshes changed passages synchronously and can be slower on large libraries. No hosted inference or automatic model download is provided.

`workspace_backup.py` adds a distinct local archive format, `mnemos-workspace-backup-v1`. An allowlist covers the vault, skill builds, analysis requests/proposals, inbox, and sanitized portable configuration. SHA-256 checks cover every entry; restore rejects traversal, duplicate/uncovered entries, symlinks, over-limit archives, and nonempty destinations. Recovery stages into a sibling directory and leaves the resulting workspace inactive. Repo identities persist; paths can be remapped. Credentials, connection profiles, sharing approvals, local indexes, Git history, external checkouts, and personal Obsidian settings do not restore. Automatic refresh, pushing, semantic search and assistant mode reset to inactive/local. Current limits are 512 MB and 20,000 files. Full workspace recovery is intentionally local; existing privacy-governed vault/cloud and Git exports remain separate.
