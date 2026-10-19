# Session summaries, local meaning search, and complete recovery

These tools are available to the local owner in Mnemos 0.13.0. They work with the same dedicated vault and project map as the rest of Mnemos. Shared author/reader tokens cannot manage the private inbox, recovery, or semantic index.

## Summarize a day or work session

1. Click **Summarize my session** in Library or the native Mac Overview. You can also open **Tools → Session inbox**.
2. Set the title and time range (displayed in your browser's local timezone), choose a project if useful, and review the selected notes. Notes updated during the period are preselected, excluding examples and archived notes. You can select older notes for background. Up to 20 sources and 150 KB of combined evidence fit in one session.
3. Paste what you worked on or append a text/Markdown chat export. Include outcomes, reasons, actual checks, unsuccessful attempts, and unfinished work. Repository activity comes from already-captured project context; refresh in Projects first when needed. Mnemos does not read other chats, uncommitted files, or all of your computer activity.
4. Choose **Start session summary**. This stores evidence in the private inbox without changing library notes. It also prepares a simple evidence work log, explicitly labeled as unverified collection rather than an AI summary.
5. For AI summarization, review the evidence and choose **Prepare AI summary**. Selected note versions need current AI approval in Privacy & sharing. Review pasted context and confirm it may be shared. Download the handoff and attach it to your existing ChatGPT, Claude, or local agent. No tunnel or API key is required, and Mnemos uploads nothing itself.
6. Import the assistant's JSON file or open **Paste or edit response JSON**. Choose **Preview proposed changes**. Review the reason, cited sources, possible duplicate titles, rendered documentation, and exact body diff.
7. Save each reviewed item separately. **Create** adds a new draft; **update** replaces a selected note's body and returns it to draft; **combine** creates a consolidated draft with links to at least two source notes and preserves the originals. The source relationships participate in the knowledge brain and privacy checks. Saved procedures can subsequently become skill candidates using the existing Skills workflow.

Return to the inbox after restarting to resume. Proposal changes clear the preview; saving requires the exact reviewed proposal. Changed source versions require a new collection. Repeating an acknowledged save does not create another note. This is individual draft review, not an atomic multi-note transaction. If the service fails between an update and its inbox acknowledgement, inspect the note before retrying. Remove old inbox sessions when no longer needed; saved documentation remains. Up to 500 records are retained until explicitly removed.

You can skip AI and review/save the evidence work log, or edit its JSON. A skill or file handoff supplies instructions; it cannot grant a cloud assistant access to your other conversations.

## Search by meaning

Keyword search remains the default. Meaning search is optional and uses an installed local Ollama service and embedding model. It does not generate answers; it ranks possible matching notes and provides source-linked excerpts.

1. Install/start Ollama from its official distribution.
2. Install one supported local embedding model: `embeddinggemma` (default), `nomic-embed-text`, or `all-minilm`. For example, run `ollama pull embeddinggemma` in a terminal. This model download needs internet, disk space, and any organizational approval applicable to your workstation. Mnemos does not initiate it.
3. Open **Search settings** from Library, or Backups & settings. Enable local meaning search, select the model you installed, and save.
4. Click **Build / refresh local index**. On large libraries the first build may take several minutes. Later searches refresh changed passages in the selected scope. A single refresh is limited to 5,000 new passages.
5. Choose **Meaning + keywords** in Library or Find context. Ask a natural question such as “how do I renew service identity?” even if the note uses “certificate rotation.” Keep exact keyword search for identifiers and error messages.

Only `127.0.0.1:11434` is contacted; no hosted URLs, proxy redirects, API credentials, or tunnels are used. Model digest and note revisions invalidate stale vectors. Model/network errors show an actionable message; there is no silent cloud fallback. Archived notes and superseded repository snapshots are excluded. Similarity can be imperfect and is not proof of correctness. The local owner still sees draft labels and source references.

Disabling the option removes the private derived index, but does not uninstall the model. The index lives outside the vault and is not included in exports or workspace backups. Rebuild it after recovery. Protect and trust the local Ollama service.

API details follow [Ollama's embedding API](https://docs.ollama.com/api/embed) and [embedding guidance](https://docs.ollama.com/capabilities/embeddings).

## Complete workspace backup and guided restore

Use **Backups & settings → Complete workspace backup & recovery** or its entry in the Mac Backups panel. This is separate from the existing vault-only snapshot and documentation Git remote backup.

The complete content archive includes:

- Vault Markdown, attachments, workflows, project definitions, maps, and privacy policies.
- Saved skill builds with their sources, AI analysis requests and accepted proposals.
- Session inbox evidence, proposals, and save records.
- Owner identity, repository registrations/source selections, and portable settings.

It excludes runtime credentials/token hashes, connector profiles, sharing approvals, personal Obsidian settings/plugins, Git history, earlier backup archives, derived search indexes/models, external engineering checkouts, and externally installed skills. External skill folder paths are retained only as a reconnection checklist after recovery. Backups do not copy project source repositories themselves.

Choose an absolute local backup folder outside workspace content directories. A protected external disk is useful. The archive and companion SHA-256 file are plaintext; Mnemos does not encrypt them. A cloud-synced folder can upload private content independently. This format has no cloud upload action. Existing rclone/Git features retain their own privacy controls and vault-only scope.

To recover:

1. Enter an archive ZIP path and a new or empty destination folder, then inspect it. Every archived file's size and checksum is verified. Unexpected members, traversal, symlinks, duplicate names, corruption, and archives exceeding 512 MB / 20,000 files are rejected.
2. Review repository paths. Supply existing local Git checkouts on the new computer, or leave a missing path blank to reconnect later. Source notes and stable repository IDs are preserved; no repo is cloned or refreshed.
3. Review the final destination and restore. Existing populated workspaces are never overwritten. The current active workspace remains selected.
4. Open Workspace setup and select the restored directory when ready. Reconfigure backup storage, assistant connections, external skill folders, and sharing approvals. Automatic repository refresh, Git pushing, and meaning search remain off until deliberately configured again. The restored `recovery.json` lists external skill folders to reconnect.

Checksums detect corruption against the manifest, not publisher identity. Restore a trusted archive. Direct edits from other applications are not coordinated by Mnemos's storage lock; avoid concurrent edits while making a recovery point.

## Local automation interface

The same operations are exposed through the local CLI. Requests are JSON files; no secrets are needed. Commands default to the selected workspace unless `--data` pins a path.

```sh
python -m mnemos session-inbox list
python -m mnemos session-inbox create --file session-request.json
python -m mnemos session-inbox handoff --file reviewed-handoff-request.json
python -m mnemos session-inbox review --file returned-proposal.json
python -m mnemos session-inbox accept --file reviewed-item.json
python -m mnemos workspace-backup create --file backup-request.json
python -m mnemos workspace-backup preview --file restore-request.json
python -m mnemos workspace-backup restore --file reviewed-restore.json
python -m mnemos semantic-search status
python -m mnemos semantic-search configure --file search-settings.json
python -m mnemos semantic-search rebuild
python -m mnemos semantic-search search --file search-request.json
```

A collection request contains `title`, ISO `start`/`end` with timezone, `project_id` (optional), `source_ids`, and `context`. Handoff uses `id` and `reviewed_context: true` after review. Proposal review takes `{id, proposal}`; `proposal` uses `format: mnemos-session-proposal-v1`, `session_id`, and `items`. Each item contains `action`, `target_id`, `title`, `type`, `summary`, Markdown `body`, `reason`, and `source_ids` (selected note IDs or `session-notes`). Accept uses `{id, index, review_revision}` from the exact preview.

Workspace backup creation takes `{destination}`. Recovery preview takes `{archive, destination, repository_paths}` where paths map registered IDs to current local checkout paths. Submit the same fields plus the returned `review_revision` to restore. Search configuration takes `{enabled, model}` and a search takes `{query, project_id, type}`. Local-owner HTTP routes mirror these operations under `/api/session-inbox`, `/api/workspace-backup`, and `/api/semantic`; mutation requests require the current workspace header and launcher authorization.
