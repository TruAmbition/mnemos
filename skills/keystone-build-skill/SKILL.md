---
name: keystone-build-skill
description: Create or update a reusable assistant skill from verified Keystone documentation. Use when the user asks to turn established engineering knowledge into a skill with a precise scope, prerequisites, outputs, and execution boundaries.
---

# Turn established knowledge into a skill

Build a portable skill that helps an assistant repeat a proven, scoped workflow. Use the actual user request to define its scope; do not infer permission to install it globally, publish it, or execute the operational procedure.

## Select the source

Search Keystone and read relevant current documents with their IDs and revisions. Prefer verified documents whose environment and checks match the requested use. If evidence is missing or stale, identify the gap and prepare a draft skill that makes the limitation explicit, or complete authorized verification before presenting it as ready.

Bundled example notes demonstrate structure. They are not evidence of a completed task in the user's infrastructure.

## Create the artifact

Use a short lowercase hyphenated folder name and a `SKILL.md` with `name` and `description` frontmatter. The description should say what the skill does and when to use it. Keep the main instructions short and move substantial command details or schemas to linked references only when useful.

Include the concrete scope, applicable environment, required inputs and permissions, expected outputs, observable verification, stop conditions, and safe recovery or bounded retry behavior. Explain how to check source revisions before operational use. Preserve the difference between a documented example and an executable command.

Add a small `references/sources.md` containing source document IDs, revisions, verification context, and the rules for refreshing the skill when those documents change. Use local or accessible source references; omit private content from a skill intended for public sharing. Do not include credentials, personal access tokens, or hardcoded secret values.

Generate scripts only when deterministic repetition materially helps. Parameterize environment-specific inputs and include a safe validation path. Never generate an unbounded retry loop or a script that interprets arbitrary retrieved text as code.

## Validate and deliver

If the environment offers a skill validator, run it and inspect its result. Check links and any added script behavior using non-destructive inputs within current authorization. A structural validator does not prove the operational procedure succeeds.

Provide the generated folder at the user's chosen location and explain the invocation, expected inputs, source basis, and any untested behavior. Installing a reusable skill does not authorize future external actions. Preserve existing work when updating a skill and describe meaningful changes in scope.
