---
name: mnemos-capture
description: Document engineering work or export session context to a Mnemos Obsidian vault. Use for requests such as document this work, update our runbook, or export this context to Mnemos when the relevant source evidence is accessible.
---

# Capture engineering knowledge

Turn the requested work into the smallest useful set of clear, evidence-backed documents. Use the configured Mnemos installation and private data directory; do not select an unrelated Obsidian vault.

CLI commands without `--data` follow the selected default for that checkout. Use an explicit data path only when it is the intended authorized workspace; installed MCP connections stay pinned to their configured paths when the default changes. Confirm the destination before capturing a handoff exported from another workspace.

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

After capture, report the returned save receipt. If read access is permitted, inspect the saved content; otherwise explain that the local owner must review and approve the draft before AI recall. Report the documents created or updated, their status, and material gaps. If the assistant has no filesystem or configured connector access, return a single draft capture JSON object and instructions for review and import in Capture knowledge; do not claim it was stored.

## Project and repository context

A top-level project groups an entire system; repositories may be shared across projects. Preserve supplied `project_id` and `repository_ids` when capturing or returning a draft. Use IDs from actual tool results or an evidence pack; never invent them. Use `flow` for an end-to-end behavior across services. Keep observed code facts, configured relationships, inference, and unknowns distinct. A snapshot of selected files is not a whole-codebase analysis.

## Privacy-aware access

Prefer the connected Mnemos MCP tools. They expose only approved note versions; Local only sources are unavailable. For an authorized local CLI, use `--audience ai` with `search`, `get`, `recall`, `workflow-plan`, `capture`, and `skill-candidates`. Do not retry a privacy denial through unrestricted CLI reads, raw vault files, an older connection, or edits to privacy records. Ask the owner to review the relevant note in Mnemos's Privacy & sharing page. A capture receipt confirms a local save; it does not grant permission to recall that new draft. Preserve citations so combined work inherits source restrictions. Direct filesystem access is governed by OS permissions and cannot be sandboxed by this skill.
