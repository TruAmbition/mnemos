# Portable context and capture formats

## Context pack input

The portal's Cloud handoff page exports a JSON object with `format: "mnemos-context-pack-v1"`, the task query, generation time, selected `documents`, and a `recall` preview. By default, the pack contains bounded recall excerpts plus source metadata; full source bodies are included only when the user explicitly selects them. Each document can carry `id`, `title`, `type`, `status`, `revision`, `summary`, `body`, `sources`, `related_ids`, and `example`. A Markdown export conveys the same selected source content with human-readable source IDs and revisions.

Full selected documents and short recall excerpts serve different purposes. Use the full document when updating it. If the user supplies only an excerpt, do not assume omitted sections are empty or reconstruct them. Do not copy the context-pack wrapper into the capture result.

A revision identifies the exported source version. It is not proof that the live vault has not changed. `example: true` marks illustrative content, not the user's verified engineering work.

## Single draft capture output

Return one object shaped like this, replacing illustrative text with supported facts:

```json
{
  "title": "Task handoff title",
  "type": "context",
  "status": "draft",
  "project": "Project from the supplied evidence",
  "summary": "One sentence about the known state and the next action.",
  "tags": ["handoff"],
  "sources": [],
  "related_ids": [],
  "body": "# Task handoff\n\n## Goal\n\nDescribe the requested outcome.\n\n## Current state\n\nSeparate completed work from proposals.\n\n## Decisions and rationale\n\nPreserve supported reasons.\n\n## Verification\n\nRecord checks actually performed and unknowns.\n\n## Next actions\n\nState bounded next steps.\n",
  "example": false
}
```

Supported types are `context`, `runbook`, `knowledge`, `troubleshooting`, `decision`, `work-log`, and `microtask`. `sources` and `related_ids` are arrays of strings. A source reference can include a supplied document ID and revision as `Mnemos document <actual-id>, revision <actual-revision>`; do not use the angle-bracket illustrations literally. Keep `related_ids` to actual known IDs. File handoff captures always create a new draft and omit `id` and `revision`. Preserve source versions in `sources`; keep relationships in `related_ids`. Updating an existing note is a separate local editor or authorized MCP/CLI operation with a current target revision.

The import preview is followed by a local save. It is not automatic verification, execution, or publication. The owner's later review determines whether the draft should become verified.
