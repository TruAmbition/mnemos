# History, answers, and documentation health

Mnemos 0.14.0 adds three local-owner tools. Open them from the web navigation or the native Mac manager. They use the selected workspace and work without a tunnel. Connected assistants and team tokens cannot access these private management endpoints.

## Recover an earlier note

Open a note and choose **History**, or use **Tools → Note history**. Select the note and a saved version, compare the complete Markdown diff, then choose **Restore as a new draft**. Missing notes remain selectable in the history page and can be recreated. The current version stays in history, so a restore can itself be undone by restoring that checkpoint.

Every Mnemos save retains the previous bytes and the new version. Reading the local library also checkpoints the versions it observes, including edits made in Obsidian. History begins with the first observation after upgrading; it cannot recover edits made and replaced between observations, or versions from before installation. Identical bytes are stored once per note. Checkpoints include the full file, timestamp, origin, and SHA-256 revision.

Restore requires a preview bound to the exact current revision and historical content. It preserves custom frontmatter, but makes the result a draft, refreshes author and update date, and regenerates managed related links. Prior verification and AI approval do not carry forward. Existing historical privacy dependencies remain restrictive. A changed or corrupt checkpoint is rejected. Very large or unsupported external notes still have to meet the normal capture limits to restore through Mnemos.

History is private plaintext under `note-history/`, outside the Obsidian vault. It is included in **complete workspace backups**, but excluded from ordinary vault ZIPs, Git documentation backup, reader exports, and cloud assistant access. Copies of text removed from a note can remain in history and older backups. There is no automatic pruning; account for this when sizing and protecting your local storage. This is local undo, not a replacement for a backup on a separate device.

## Ask a question across notes

1. Open **Ask my library**, enter a specific question, and optionally select a top-level project.
2. Choose keyword retrieval or the separately configured local meaning search. Alternatively select up to six current notes explicitly.
3. Click **Find sources**. Review titles, source revisions, verification labels, excerpts, and evidence-change warnings. This step performs retrieval only; it does not invent an answer.
4. Choose one of the answer routes below.
5. Read the answer and expand each claim's supporting evidence. Inspect gaps and uncertainty. Optionally save a new **draft** with related-note links and revision-bound source references.

Saved questions and answers persist privately outside the library under `library-answers/`. Reopening a question checks whether its source content, provenance, or privacy settings changed. Historical results remain readable with a warning, but answering, sharing, or saving from changed evidence requires collecting fresh sources. Removing a question leaves an already saved draft intact. Repeated saves open the existing draft rather than replacing edits to it.

### Existing ChatGPT or Claude account

Choose **Prepare assistant handoff**. Each selected source needs current approval in **Privacy & sharing**; source policy and best-effort credential checks still apply. Review and download the question and evidence file, attach it to the assistant you already use, and ask it to answer. Import or paste the returned JSON with **Check citations & show answer**. There is no API key, tunnel, automatic upload, or embedded account login. A ChatGPT/Claude subscription is not used as an inference API by Mnemos.

The response format is `mnemos-library-answer-v1`:

```json
{
  "format": "mnemos-library-answer-v1",
  "request_id": "answer-0123456789abcdef",
  "claims": [
    {
      "text": "The documented recovery starts by restoring the previous release.",
      "kind": "fact",
      "citations": [
        {"source_id": "release-recovery", "quote": "Restore the previous release after a failed deployment."}
      ]
    }
  ],
  "unknowns": ["The supplied excerpts do not identify the production environment."]
}
```

Use the actual request ID and source IDs from the handoff. Each of at most 12 claims needs 1–6 citations. Quotes must be 20–600 characters and match the selected summary or excerpt, with whitespace normalization. Use `kind: inference` for deductions and list conflicts or missing evidence under `unknowns`. An insufficient answer may return no claims and must explain the gap. Invalid IDs, unmatched quotes, malformed or oversized responses, and stale evidence are rejected.

Citations prove that the quoted passage exists in the selected evidence. They do **not** prove the interpretation or operational correctness of the answer. Excerpts can omit important surrounding context. Source status is a recorded label, not an automated test result. The UI keeps these limitations visible and never marks an answer verified automatically.

### Optional local model

Install and start Ollama separately, with a local text-generation model that supports completion. Choose **Use a local model**, select an installed model, and click **Generate local answer**. No model is downloaded automatically. Meaning-search embeddings and answer generation are separate capabilities; an embedding-only model cannot generate an answer.

Mnemos connects directly to `127.0.0.1:11434`, bypasses proxy configuration, rejects redirects, excludes models marked as cloud/remote, checks completion support, and sends only the displayed question and bounded source excerpts. This route works with local-only notes without cloud-sharing approval. No tools or commands are supplied to the model. Output still passes the same citation validator. Model availability, hardware, timeouts, and response quality can affect success; malformed or incomplete output is reported as an error, with file handoff available as an alternative. Mnemos cannot control independently modified Ollama servers or workstation-level logging.

The implementation uses Ollama's documented [chat endpoint](https://docs.ollama.com/api/chat) with non-streaming structured output. The application bundles neither model weights nor an inference engine.

## Review documentation health

Open **Tools → Documentation health**. Filter by project and finding type. The page explains each finding and opens the affected note or saved skill:

| Finding | Why it appears | What to do |
| --- | --- | --- |
| Changed source evidence | A cited revision, source availability, project definition, or captured repository snapshot changed. | Compare current evidence, update the explanation and source references, then verify it. |
| Unverified procedure | A runbook, troubleshooting note, microtask, flow, or skill note is still a draft. | Validate prerequisites, steps, expected results, and recovery in the intended environment. |
| Verification review due | A verified note has no usable verification date, or its last verification is older than the configured interval. | Recheck the procedure and save its current verification; age alone does not make it incorrect. |
| Open questions | Explicit TODO/FIXME/TBD markers, unchecked tasks, or populated questions/unknowns sections appear in the text. | Answer the question or record the outstanding limitation. This is a text check, not AI interpretation. |
| Skill needs review | A saved package has changed/missing source evidence, or it was built from unverified sources. | Review the original notes and rebuild a package when ready. Existing installed skills are not modified. |

Examples, archived notes, and superseded captured repository snapshots are excluded. The default review interval is 90 days, configurable from 1–730 days. A finding can be snoozed for seven days in the UI; the CLI also supports 30 days. Snoozing never verifies documentation. It expires automatically and stops applying when the finding's evidence changes. Use the Snoozed view and **Review now** to bring it back early. Resolved findings disappear on refresh. Multiple findings may refer to one note.

The queue compares saved evidence. It does not fetch Git remotes, scan uncommitted code, or establish that a procedure has been exercised. Health snoozes live under `health-state/`; the review interval lives in configuration. Both are included in complete workspace recovery.

## Local automation interfaces

All commands accept optional `--data /absolute/workspace` and request JSON through `--file request.json`:

```text
python -m mnemos note-history list|preview|restore
python -m mnemos library-answers list|create|read|handoff|accept|models|generate|save|remove
python -m mnemos documentation-health list|configure|snooze
```

Matching loopback-owner HTTP endpoints are `/api/note-history`, `/api/library-answers`, and `/api/documentation-health`, with operation names as suffixes. Note history preview/restore uses `{id, revision, review_revision}` (omit the review token for preview). Answer creation uses `{question, project_id?, method?, source_ids?}`; operations use `{id}`, import adds `answer`, generation adds `model`, and saving adds the returned `answer_revision`. Health snooze uses `{id, fingerprint, days}` and interval settings use `{review_days}`. Use the existing local authentication and active-workspace guard; these APIs are not exposed in the cloud Actions schema or MCP tool set.
