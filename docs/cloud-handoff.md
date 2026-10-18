# Cloud handoff without a tunnel

Mnemos can exchange knowledge with a cloud chat through files. Your local library stays on your computer; you choose which source material to upload and later review the returned draft before saving it. No tunnel, public server, account connector, or direct Mac access is required.

Company policies and the selected AI service's data rules still govern uploads. A file handoff avoids a persistent connection; it does not make uploaded information local-only. This route is useful when you want to choose sources for each task. Its tradeoff is manual transfer and a snapshot that can become stale; a tunnel supports live lookup and direct draft updates but grants the current connector access to the entire dedicated vault, including drafts. See [the comparison](chatgpt-tunnel.md#is-a-tunnel-worth-it).

## Send the relevant context

1. Open **Cloud handoff** in the local Mnemos portal and describe the work you will do.
2. Inspect the suggested sources. The default recall preview is bounded; selecting full documents includes more content than the preview. Choose only material appropriate to share.
3. Download the context pack as JSON or Markdown, or copy the bounded context. Copied excerpts stay within the selected character budget, including their preamble and source headers. Source IDs, revisions, verification status, and example labels travel with the material. Downloaded packs keep the full handoff instructions separately and can include the full documents you explicitly selected.
4. An author or owner can download the portable skills ZIP from the handoff page if useful. Readers can ask an author or owner for the skill files; the CLI skill export packages only public bundled instructions and does not require a vault. `mnemos-handoff` is the file-based routine; it contains instructions and its format reference, not private notes, access tokens, or connection credentials.
5. Attach the chosen context and handoff skill/reference files to your cloud chat using that client's supported upload or skill mechanism. Upload support varies by client; if ZIP installation is unsupported, extract the relevant skill and supply its `SKILL.md` and reference file.

Ask the assistant to use the supplied sources for the task and return one draft capture JSON when the useful work is complete. The skill distinguishes observed results from suggestions and leaves missing facts unknown.

## Bring the result back

The assistant returns one JSON object with `title`, `type`, `status: "draft"`, `project`, `summary`, `tags`, `sources`, `related_ids`, and Markdown `body`. It should include only supported facts, explicit unknowns, and non-secret inputs. The file workflow creates a new draft and omits `id` and `revision`. Source revisions remain provenance in `sources`, with relationships in `related_ids`.

Open **Capture knowledge**, import the JSON file or expand **Paste JSON instead**, paste the returned JSON, and choose **Preview pasted draft**. Inspect the preview, source references, and related document IDs. Previewing does not save anything. Save after reviewing it. Mnemos creates a managed **Related knowledge** section for IDs that resolve to existing notes, allowing Obsidian to show links and backlinks. An unresolved ID is retained as metadata rather than being converted into an invented note link.

Portal import always creates a new draft; it does not overwrite an existing page. To update an existing note, use its editor or an authorized local MCP/CLI workflow that reads its current revision and reconciles changes. The imported draft remains unverified until the owner reviews its stated scope.

## Command-line alternative

From an installation you can actually access:

```sh
python3 -m mnemos handoff "deployment recovery" --budget 6000 --output context-pack.json
python3 -m mnemos skills-export --output mnemos-skills.zip
python3 -m mnemos capture --file /path/to/returned-draft.json
```

These commands use the workspace selected in setup. Add `--data /absolute/path/to/private-data` to pin `handoff` or `capture` to a specific authorized workspace. Confirm that an import belongs to the intended library if the default changed after export. Repeat `--id actual-source-id` to explicitly include full selected source documents. The bounded preview is measured in characters. Full selected source content has a separate 200 KB limit. Skill export does not require an initialized vault because it packages only the bundled source skills.

The local HTTP equivalents are `GET /api/handoff?query=...&budget=...` with optional repeated `id` parameters, and `GET /api/skills/export`. They do not upload material to an AI provider. The existing capture interface accepts one reviewed document, not a context-pack wrapper or an array of documents.

## What the assistant can access

A cloud chat can use the material you provide and any tools actually connected to it. A pathname in an attachment does not grant access to your computer. Mnemos cannot automatically inspect every prior ChatGPT, Claude, or Codex chat. A source revision describes what was exported; it is not proof that the live vault remains unchanged.

For a local client that has authorized filesystem access, [local MCP setup](assistant-connections.md) offers direct capture and recall without a tunnel. Existing [tunnel](chatgpt-tunnel.md) and [hosted Actions](cloud-chatgpt.md) routes remain optional, separately configured connections.
