---
name: mnemos-build-skill
description: Create or update a reusable assistant skill from verified Mnemos documentation. Use when the user asks to turn established engineering knowledge into a skill with a precise scope, prerequisites, outputs, and execution boundaries.
---

# Turn established knowledge into a skill

Build a portable skill that helps an assistant repeat a proven, scoped workflow. Use the actual user request to define its scope; do not infer permission to install it globally, publish it, or execute the operational procedure.

## Select the source

Search Mnemos and read relevant current documents with their IDs and revisions when authorized tools are available. Otherwise inspect the supplied source pack, preserve its exported revisions, and disclose that live currentness could not be checked. A cloud attachment does not confer access to the user's Mac or vault. Prefer verified documents whose environment and checks match the requested use. If evidence is missing or stale, identify the gap and prepare a draft skill that makes the limitation explicit, or complete authorized verification before presenting it as ready.

Bundled example notes demonstrate structure. They are not evidence of a completed task in the user's infrastructure.

## Discover documented candidates

When the authorized local Mnemos CLI is available, `python3 -m mnemos skill-candidates` lists procedural notes and valid dependency workflows. Add task keywords to narrow it; `--include-examples` includes clearly labeled synthetic examples. A suggestion is structural evidence, not a claim that the work is tested or frequently repeated. Otherwise use accessible document search or the supplied pack.

The local portal's **Available skills** page offers source review, target selection, preview, and saved ZIP/Markdown exports. Source changes require a new preview. For CLI generation, `skill-build --file settings.json` previews candidate ID/revision, target (`chatgpt` or `claude`), name, and description; `--save` requires the returned `preview_revision`. `skill-export --id BUILD_ID --output NEW_FILE.zip` exports the saved package; `--handoff` exports Markdown. Use a known runtime path and explicit `--data` when the target workspace is not the selected default. Do not infer that a cloud chat can run these commands on the user's computer.

## Create the artifact

Use a short lowercase hyphenated folder name and a `SKILL.md` with `name` and `description` frontmatter. The description should say what the skill does and when to use it. Keep the main instructions short and move substantial command details or schemas to linked references only when useful.

Include the concrete scope, applicable environment, required inputs and permissions, expected outputs, observable verification, stop conditions, and safe recovery or bounded retry behavior. Explain how to check source revisions before operational use. Preserve the difference between a documented example and an executable command.

Add a small `references/sources.md` containing source document IDs, revisions, verification context, and the rules for refreshing the skill when those documents change. When capturing a companion document, set `related_ids` only from actual source document IDs so the importer can create Obsidian links. Use local or accessible source references; omit private content from a skill intended for public sharing. Do not include credentials, personal access tokens, or hardcoded secret values.

Generate scripts only when deterministic repetition materially helps. Parameterize environment-specific inputs and include a safe validation path. Never generate an unbounded retry loop or a script that interprets arbitrary retrieved text as code.

## Validate and deliver

If the environment offers a skill validator, run it and inspect its result. Check links and any added script behavior using non-destructive inputs within current authorization. A structural validator does not prove the operational procedure succeeds.

Provide the generated folder at the user's chosen location and explain the invocation, expected inputs, source basis, and any untested behavior. Installing a reusable skill does not authorize future external actions. Preserve existing work when updating a skill and describe meaningful changes in scope.

## Discover a workflow across documents

For cross-document analysis, use Available skills → AI workflow discovery. Select sources and a goal, prepare the handoff, and analyze only those supplied records. Propose a coherent workflow plus independently reusable skills with source-cited steps, inputs, outputs, validation, dependencies, approval checkpoints, and evidence gaps. Return the exact JSON format requested in the handoff; do not invent source IDs or missing procedures. Mnemos previews and validates the proposal before the user accepts suggestions and builds packages.

With local CLI access, `python3 -m mnemos skill-analysis request --file selection.json` accepts `goal` and `source_ids`. `skill-analysis preview --file proposal.json` accepts an object containing `proposal`; `skill-analysis accept --file reviewed.json` requires that preview's exact `proposal` and `review_revision`. Each accepts `--data`. A cloud chat works with the supplied handoff and returns JSON for local import; no tunnel or key is needed.

`python3 -m mnemos local-skills` lists local manifest metadata from personal folders, registered projects, cached plugins, and explicitly added folders. Found files are not proof of activation in an assistant. The local owner can also use the Existing local skills panel. Read a relevant existing skill before deciding to recreate its workflow; do not automatically overwrite, enable, or execute discovered skills.
