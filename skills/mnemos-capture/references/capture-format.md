# Capture interface

Use these commands only when the current assistant has authorized filesystem access to the intended installation. Otherwise return a single draft JSON object for the user to review and import; no tunnel is required. Run commands from the Mnemos source directory using Python 3.11 or later. Resolve the user's actual data directory before writing; `./data` below is an example.

These examples use the checkout's selected default workspace. An explicit `--data /absolute/path/to/private-data` pins an authorized destination and bypasses default switching.

```sh
python3 -m mnemos search "deployment credentials"
python3 -m mnemos get --id existing-document-id
python3 -m mnemos capture --file ./work/capture.json
```

The JSON file contains one document. Use a private scratch directory for capture input; do not commit it with the toolkit source.

```json
{
  "title": "Descriptive title for the documented outcome",
  "type": "runbook",
  "status": "draft",
  "project": "Project name",
  "tags": ["component", "task"],
  "sources": [],
  "related_ids": [],
  "summary": "One sentence explaining what this document helps someone do.",
  "body": "# Descriptive title\n\n## Purpose\n\nEvidence-backed explanation.\n\n## Verification\n\nState the checks actually performed and remaining gaps.\n",
  "example": false
}
```

For an update, add the existing `id` and its exact current `revision`. The app derives author identity from the configured owner or authenticated author credential. Do not invent an author, verification date, source link, successful check, or revision.

Preferred document types are `runbook`, `knowledge`, `troubleshooting`, `decision`, `work-log`, `microtask`, and `context`. Status is `draft`, `verified`, or `archived`. The content is Markdown; metadata fields carry plain values. `sources` contains available source references and source revisions. `related_ids` contains only actual related Mnemos document IDs obtained from accessible sources. Mnemos creates Obsidian links from those IDs when saving; do not invent titles, paths, or IDs. `example: true` marks illustrative content and must stay true for bundled examples unless rewritten as real, independently evidenced work.

When local MCP is connected, use `search_documents(query)`, `read_document(id)`, and `capture_document(document)` with the same document shape. Captures run with author permissions; the owner reviews and verifies them. A cloud chat without a connected tool or accessible checkout can produce this JSON for manual import, but cannot claim it saved to the local vault.

If the current CLI or connector differs from this reference, inspect its `--help` or tool schema. Use the installed supported interface rather than guessing a request. Never place a bearer token inside the capture JSON, a document, or a command saved as documentation.
