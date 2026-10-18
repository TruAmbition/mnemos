# Available skills

Mnemos finds documented procedures you could reuse as assistant skills. Open **Available skills** in the local portal. Owner and author accounts can build; readers and the static reader cannot access private generated packages.

## Build a skill

1. Find a task or project. Review the source documents shown on a suggestion.
2. Choose **Build skill**. Select **ChatGPT / Codex** or **Claude**.
3. Set a short lowercase name and a description explaining when the assistant should use it.
4. Choose **Preview skill** and review the generated instructions and included files.
5. Choose **Save skill**, then download the ZIP or cloud handoff Markdown.
6. Use the package in your chosen assistant and test a representative task before relying on it.

Building is local and requires no tunnel, model API key, or inference service. It creates instruction files; it does not execute a workflow or install anything in an account. Your existing notes remain unchanged.

## What suggestions mean

Candidates include non-archived runbooks, troubleshooting notes, microtasks, skill documents, other documents with a procedure heading and multiple numbered steps, and valid workflow dependency plans. Search matches the candidate title, project, and explanation. This is structural discovery, not semantic analysis of your activity or proof that you repeat a task frequently.

**Verified sources** means the referenced records are marked verified, not that the new package has passed an operational test. **Review needed** identifies unverified sources. Bundled **Examples** are hidden unless you enable them and remain explicitly labeled. Invalid workflow plans appear as warnings rather than buildable suggestions.

A workflow package preserves its existing dependency order and approval checkpoints. Mnemos does not invent a multi-step orchestration plan by combining unrelated notes. For a new orchestration, use the workflow planner or an assistant to draft and validate that plan first.

## Use the output

| Target | How to use it |
| --- | --- |
| Local ChatGPT desktop / Codex | Extract the skill folder into the selected project's `.agents/skills` directory, preserving existing skills. Reopen the project as needed and invoke the skill. |
| ChatGPT cloud chat | Attach the single Markdown handoff and ask the assistant to follow it for the requested task. This provides context for the chat; it does not install a persistent web skill. Native web distribution uses a plugin. |
| Claude | Where your account permits custom skills, use Customize → Skills → Create skill → Upload a skill and select the ZIP. Enable it and test it. |
| Other file-capable assistants | Supply the Markdown handoff and specify the task, environment, and available tools. |

Platform capabilities and organization policies vary. See the official [OpenAI skill guide](https://learn.chatgpt.com/docs/build-skills) and [Claude skill guide](https://support.claude.com/en/articles/12512180-use-skills-in-claude).

The ZIP contains one named folder with `SKILL.md`, `references/sources.md`, and full source Markdown files. The handoff combines the same instructions and sources in one readable file. Neither output grants live access to Mnemos, connects to your workstation, or guarantees tool availability. Review the source contents before uploading them to another service.

## Keep skills current

Saved packages are immutable snapshots. **Built skills** shows **Sources unchanged**, **Sources changed — rebuild recommended**, or **Source unavailable**. A source change between discovery, preview, and save requires refreshing and reviewing it again. Rebuilding creates another saved build; it does not overwrite a previously installed skill. Update that installation explicitly after review.

Packages are saved under the active data folder's `skill-builds/` directory. They are private runtime data and should not be committed to the public source repository. The existing vault-only backup excludes these generated files: retain downloaded ZIPs or back up this directory separately. Source notes and workflow definitions can recreate a package, but cannot necessarily recreate an old snapshot after those sources change.

## Local assistant / CLI workflow

With authorized access to this installation, an assistant can discover candidates:

```sh
python3 -m mnemos skill-candidates "cache"
python3 -m mnemos skill-candidates --include-examples
```

Create a JSON settings file using an actual returned candidate ID and revision:

```json
{
  "candidate_id": "document:your-document-id",
  "revision": "copy-the-current-candidate-revision",
  "target": "claude",
  "name": "restore-project-cache",
  "description": "Restore this project's cache when asked to repeat its documented recovery procedure."
}
```

Preview without saving:

```sh
python3 -m mnemos skill-build --file settings.json
```

After reviewing the output, add its exact `preview_revision` to the settings JSON, then save and export using the returned build ID:

```sh
python3 -m mnemos skill-build --file settings.json --save
python3 -m mnemos skill-export --id skill-RETURNED_ID --output new-skill.zip
python3 -m mnemos skill-export --id skill-RETURNED_ID --output handoff.md --handoff
```

Use `target: "chatgpt"` for the other target. Every command accepts `--data` to pin an explicit workspace; otherwise the active default applies. Export refuses to overwrite an existing output. The bundled `mnemos-build-skill` skill documents this process. The five existing MCP tools have not been expanded; a cloud assistant without filesystem/CLI access must use file handoff or other available connected tools.

## Limits

A package supports up to 20 source documents and 200 KB of complete instruction/reference text, without silent truncation. Each workspace retains at most 200 saved builds. Manage older local build files explicitly if that limit is reached; there is no automatic deletion. Recognized credential patterns block export, but this is not comprehensive secret detection. Generated skills contain Markdown instructions and references, not generated executable scripts. Execution, validation, and any required authorization remain with the assistant and engineer.
