---
name: mnemos-capture
description: Document engineering work or export session context to a Mnemos Obsidian vault. Use for requests such as document this work, update our runbook, or export this context to Mnemos when the relevant source evidence is accessible.
---

# Capture engineering knowledge

Turn the requested work into the smallest useful set of clear, evidence-backed documents. Use the configured Mnemos installation and private data directory; do not select an unrelated Obsidian vault.

## Establish the evidence

Read the relevant accessible conversation, changes, and results. Distinguish actions that ran from proposals, and observed outcomes from assumptions. Keep the original rationale when it is supported. If a source is unavailable, state the limitation rather than reconstructing its contents.

When a Mnemos tool or authorized local installation is actually accessible, search it before drafting. Otherwise inspect the supplied source pack and mark the lack of a live search. Reuse an existing page when the problem and purpose match; preserve useful prior decisions and provenance when updating it. Do not merge distinct environments or procedures merely because they share keywords.

## Write for reuse

Choose a runbook for a repeatable procedure, knowledge item for an explanation, troubleshooting guide for symptoms and diagnosis, decision for rationale, work log for session evidence, microtask for one bounded action, or context document for resuming work in another assistant. Include only relevant sections. The vault's `Templates/` directory provides starting structures.

For context export, capture the goal, current state, constraints, decisions and rationale, failed approaches supported by evidence, unresolved questions, next actions, and source references. Preserve enough detail to resume without copying an entire transcript. Explicitly distinguish known state, inference, and missing information.

State prerequisites, applicable environment and versions, exact steps, expected results, actual checks performed, recovery guidance, and unresolved items where relevant. Retain source task links and repository revisions when available. Label examples and untested steps explicitly.

Link related knowledge using `related_ids` from source documents you actually read or IDs present in an exported pack. Mnemos creates Obsidian links from these stable IDs on save; do not guess note filenames or fabricate relationships.

Remove passwords, API keys, tokens, private keys, and unnecessary personal data. Preserve operational meaning with named placeholders. Summarize source material; do not save raw conversation dumps by default.

## Save and check

Read [references/capture-format.md](references/capture-format.md) for the CLI and JSON contract. Use the connected `capture_document` MCP tool when available and authorized, or the CLI only when this assistant can access the intended installation. A cloud chat cannot access a Mac path merely because it appears in a message. Local clients and manual file handoffs need no tunnel. Default new or materially changed procedures to `draft`; use `verified` only when available evidence supports the stated verification scope and the interface permits verification. The local MCP capture tool writes with author privileges and cannot mark content verified. A request to document work does not authorize executing the work again.

For updates, retrieve the current document and submit its current revision. If the revision conflicts, reread and reconcile the contents; never bypass the check or overwrite the vault directly to force a save.

After capture, open the saved content or retrieve it, check its metadata and evidence, and search for its title. Report the documents created or updated, their status, and material gaps. If the assistant has no filesystem or configured connector access, return a single draft capture JSON object and instructions for review and import in Capture knowledge; do not claim it was stored.
