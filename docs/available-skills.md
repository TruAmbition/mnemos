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

Each card includes **Why create this skill?**: the potential reuse benefit and the documented scope behind the suggestion. Existing workflow suggestions explain their task/source counts and approval checkpoints. AI suggestions show the accepted proposal’s rationale; smaller skills also describe their expected outputs. These explanations reuse saved evidence and do not make new model calls or claim measured time savings or repeated usage.

Candidates include non-archived runbooks, troubleshooting notes, microtasks, skill documents, other documents with a procedure heading and multiple numbered steps, and valid workflow dependency plans. Search matches the candidate title, project, and explanation. These automatic candidates use structural discovery. Accepted AI proposals appear alongside them; their reasoning comes from the assistant you use for the handoff. Neither route proves how often you repeat a task.

**Verified sources** means the referenced records are marked verified, not that the new package has passed an operational test. **Review needed** identifies unverified sources. Bundled **Examples** are hidden unless you enable them and remain explicitly labeled. Invalid workflow plans appear as warnings rather than buildable suggestions.

A workflow package preserves its existing dependency order and approval checkpoints. For a new orchestration across documents, use AI workflow discovery below. The assistant proposes the decomposition, and you review its evidence before accepting it.

## AI workflow discovery across documents

1. Select **Choose documents** and describe the workflow to look for.
2. Select 2–20 non-example source notes, up to 100 KB total. Mnemos prepares a handoff with their full text and exact revisions.
3. Review the pack, download it, and attach it to your existing ChatGPT or Claude chat. Ask the assistant to perform the analysis and return the requested JSON.
4. In **Import an AI proposal**, paste the returned JSON and select **Preview proposal**.
5. Review each smaller skill's inputs, outputs, cited steps, validation, dependencies, approval checkpoints, and evidence gaps. Open the cited source notes when needed.
6. Select **Accept as skill suggestions**. You can now build a package for the complete workflow or any of its smaller skills.

AI reasoning happens in the chat you choose, not in a model running inside Mnemos. There is no new API key, tunnel, automatic upload, or background model invocation. The assistant must return the provided `mnemos-skill-analysis-v1` format with the exact request ID. If the selected evidence cannot support a workflow, ask it to explain the gaps instead of inventing a proposal.

A proposal has 2–12 smaller skills and uses at least two selected documents. Each skill names required inputs, outputs, validation, 1–15 source-cited steps, and dependencies on other skill IDs. Mnemos rejects unknown source IDs, invalid dependencies, cycles, malformed fields, stale source revisions, and an acceptance that does not match its preview. These checks validate structure and provenance, not semantic truth: review whether each cited source actually supports its step and whether approval and recovery requirements were retained.

The complete workflow package includes all proposed skills in dependency order. A separately exported child skill includes its own source notes and dependency names; it does not install or execute the other skills. Supply and verify their required outputs before using the child alone. Accepted proposals always remain **Review needed**. Changed sources make that proposal unavailable for new builds until you perform a fresh analysis; previously saved packages remain snapshots.

Analysis requests and accepted proposals are private files in `skill-analysis/` and `skill-proposals/` under the active data folder. Each directory is limited to 100 records, with no automatic deletion. Requests contain the selected full text in the prompt. These directories, like `skill-builds/`, are outside the vault-only backup; back them up separately if you need the original analysis history.

Local CLI equivalents are `skill-analysis request --file selection.json`, `skill-analysis preview --file proposal.json`, and `skill-analysis accept --file reviewed.json`. Selection JSON contains `goal` and `source_ids`; preview input contains `proposal`; acceptance uses the preview's returned `proposal` and `review_revision`. Each accepts `--data`.

## Existing skills made outside Mnemos

Expand **Existing local skills — including skills made elsewhere**, then select **Scan local skills**. Filter by name, description, or location. This local-owner-only inventory reads SKILL.md metadata from personal `.agents/skills`, Codex and Claude skill folders, the Mnemos checkout, registered projects, and the Codex plugin cache. Add another absolute skill-folder path when needed. Personal Codex paths respect `CODEX_HOME`.

This is a read-only file inventory: it does not import, overwrite, execute, install, or enable discovered skills. Cached plugin versions may be inactive, and duplicate copies in different locations are shown separately. A skill found on disk is not proof that a particular assistant has loaded it. Skills stored only in a cloud account are not queried; export them to a local folder first. See [OpenAI's skill guide](https://learn.chatgpt.com/docs/build-skills) for native discovery behavior.

The scan skips symbolic links and oversized/unreadable manifests, reports limitations, and is bounded to 5,000 inspected entries, 500 skills, and seven directory levels. Basic scalar and folded descriptions are read; this is not a complete YAML parser. Added folders persist per workspace, up to 20. No broad home-directory scan occurs. The inventory is excluded from shared author/reader access and static exports.

Use `python3 -m mnemos local-skills` from an authorized local assistant or terminal, with optional `--folder /absolute/skill/folder` to register another folder and `--data` to pin a workspace.

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
