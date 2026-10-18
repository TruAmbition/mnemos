# Projects, repositories, and system understanding

Mnemos 0.9 separates a **project** (the whole application or platform) from a **repository** (one local Git checkout). A project can contain many repositories; a shared service can belong to several projects. Existing repository registrations and snapshots remain intact and unassigned until you create a grouping. Nothing is cloned, moved, or rewritten during this upgrade.

## Start with your system

1. Open **Projects → Create project**. Name the overall system and describe what it does.
2. Expand **Repository settings** and add the local checkouts if they are not already registered. Give each a responsibility, such as “Owns orders and publishes order events.”
3. Use **Edit project** to select its member repositories. Under **Connections & terminology**, record known relationships: calls, publishes events to, depends on, or deployed by. These are engineer-declared facts to review, not automatic code analysis.
4. Refresh each repository's context. Its source selection accepts explicit committed text files, including code such as `src/routes.py`. The default selection still favors documentation. File/count/size limits and credential exclusions remain in force; a broad glob is not a whole-codebase index.
5. Use **Search project**. Library searches, Find context, Use with AI, and Skills can all use a top-level project scope or all projects. The native macOS manager shows the same hierarchy and links directly to project search.

Changing a project name retains its stable ID. Existing notes with a matching repository label are associated without rewriting their bytes; Git snapshot references identify repository ownership even after a repository is renamed. New notes can declare `project_id` and `repository_ids`. The latter links cross-service notes to shared repositories. The free-text `project` label remains supported for old notes and external imports. Removing a grouping preserves its notes, maps, and repository registrations.

## Ask what the code does

Choose **Explain this system** on a project card. Select 1–20 current non-example documents, up to 150 KB of evidence, and ask a specific question. For example:

> Trace checkout through order creation and payment. Explain entry points, service boundaries, event contracts, failure paths, and where refunds would need changes.

Review the prepared handoff, then copy or attach it to your existing ChatGPT or Claude chat. It includes the project definition, configured relationships, repository responsibilities, selected full notes, and exact source revisions. Source snapshots contain bounded committed excerpts, including code only when explicitly selected. Local checkout paths are not added to the handoff. Notes can still contain sensitive information; inspect the pack before sharing.

The assistant returns one JSON draft with project/repository IDs, source revision references, and related-document links. Use **Import response → Paste JSON instead** (or import a file), review the preview, and save. The response remains a draft; Mnemos does not execute it, verify its claims, or silently install skills. Unsupported facts should be listed as unknowns. A cloud chat has only the attached evidence and does not gain live filesystem access.

A saved explanation displays a source-change warning when its cited note revisions, project definition, or latest captured repository snapshots have changed. This comparison uses recorded evidence, not live remote code or semantic verification. Refresh repository context to detect new local commits. Changed explanations are blocked from new skill builds until reviewed and updated; already installed skills are not changed automatically.

There is no background LLM, automatic upload, tunnel requirement, or model API key. This is an explicit evidence-and-review workflow. Complete automatic codebase indexing, inferred service graphs, and continuous AI rewriting are not implemented.

## Capture cross-service flows and make skills

Use **Capture work → End-to-end flow** to document an entire behavior. Record its entry point, participating repositories, calls/events, state changes, failure paths, and checks. Assign the top-level project; retain repository IDs when importing assistant-generated notes.

**Find skills** opens discovery scoped to the whole project. Structural suggestions find documented procedures, including Flow notes with numbered flow steps. A multi-source suggestion remains in scope only when all its sources belong to the selected project. A shared service can contribute to each parent project's workflows.

For deeper decomposition, use **AI workflow discovery → Choose documents**. Select the reviewed system explanation, relevant flow notes, runbooks, and troubleshooting records across repositories. The existing handoff/import process produces a complete workflow and smaller skills with inputs, outputs, dependencies, citations, and checks. It is not restricted to one skill per repository. Existing-skill matching still helps choose reuse, extension, or creation.

## Obsidian mind maps

**Create Obsidian map** saves a new draft project home note and a new `.canvas` file under `Maps/` in the dedicated vault. Open that Canvas in Obsidian. The parent is the project; repositories are child nodes; current documentation connects to its repository or the project. Declared service connections are labeled edges. Markdown links also make the project home useful in Obsidian Graph view.

Every generation creates new files. It never replaces an engineer-edited map. Maps are snapshots, not continuously rearranged views. The generator supports up to 80 current source documents per project. Earlier maps remain available and are excluded from subsequent map evidence to prevent recursive maps.

## Storage, recovery, and interfaces

Top-level definitions live in `vault/Projects/projects.json`, including stable IDs, purpose, terminology, repository membership, and declared relationships. Ordinary vault backups include this file, the Markdown notes, and generated Canvases. Machine-specific checkout paths and refresh settings remain in private `config.json` under the legacy `projects` key. That key and the existing `/api/projects` endpoints continue to mean repository registrations for compatibility.

After moving to another computer or restoring a vault, reconnect local checkouts and update project membership. Missing old repository IDs remain visible until replaced or removed; Mnemos never guesses paths or maps an unrelated checkout onto them. Absolute paths are not stored in project definitions or generated maps. These files are knowledge, however, and may contain private system names or design details; backups retain that information.

Project definition management, maps, and explanation handoffs use the existing local-owner, same-origin, and workspace guards. Shared readers receive only verified notes and the project names associated with those visible notes, not checkout paths or the management API. Explicit document project IDs are preserved even if their grouping is unavailable after an import.

CLI examples:

```sh
python3 -m mnemos knowledge-projects list
python3 -m mnemos knowledge-projects save --file project-definition.json
python3 -m mnemos knowledge-projects detail --id system-RETURNED_ID
python3 -m mnemos knowledge-projects analysis --file project-selection.json
python3 -m mnemos knowledge-projects map --file reviewed-project.json
python3 -m mnemos recall "checkout failure" --project-id system-RETURNED_ID
python3 -m mnemos skill-candidates --project-id system-RETURNED_ID
```

Save updates, map generation, and analysis requests require the current `id` and `revision`. Analysis also requires `source_ids` and optionally `goal`. MCP search and recall retain their existing names with an optional `project_id`; search metadata includes project IDs/names. Capture accepts `project_id`, `repository_ids`, and the `flow` document type. Restart an existing MCP process to load the updated tool schemas; no connection credentials need to change.

## Privacy (0.10)

New and existing projects default to Local only. Choose **Project privacy** when creating/editing a project, then use **Privacy & sharing** to review and approve exact note versions for AI. Shared repositories and workflows inherit the strictest source setting. See [Privacy and sharing](privacy-and-sharing.md) for the policy table, backup restrictions, local authentication, and filesystem limitations.
