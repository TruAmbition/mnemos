# Assistant connections and context handoff

Mnemos provides a local MCP server and a CLI. Both use the same dedicated vault. Local clients need no tunnel. A cloud chat can instead use the [file handoff workflow](cloud-handoff.md), which also needs no tunnel and grants no direct computer access. A local desktop connection does not automatically make the vault available to a separately hosted chat.

## Project setup for Codex and Claude Code

From the source checkout, run:

```sh
python3 scripts/install_agents.py --data ./data --client both
```

Choose `--client codex` or `--client claude` for one client. Add `--project /absolute/path/to/working-project` to configure another workspace. The installer writes only project-local Codex or Claude Code configuration and skill copies. It preserves unrelated MCP servers and reuses a matching legacy `keystone` entry without adding a duplicate. Conflicting definitions under either name are left unchanged. Reopen and trust the project in the client before checking tool discovery. This does not configure Claude Desktop; use its separate example below.

## Portable skills without a connection

```sh
python3 scripts/install_agents.py --skills-only --client both
```

This mode needs no data directory, does not inspect or modify MCP settings, and copies only bundled skills into the chosen project. Use `--project` and `--client` to narrow the destination. The portal offers `/api/skills/export` to owners and authors, or run `python3 -m mnemos skills-export --output mnemos-skills.zip`. The archive contains only named source skill folders and their references. It contains no private notes, access tokens, or account credentials.

For a cloud chat, upload the relevant supported skill files and selected context under your organization's data rules. A skill explains a routine; it does not install a connection or confer access to a local path.

## Codex local connection

Add the local server with absolute paths, replacing the illustrative paths below:

```sh
codex mcp add mnemos -- python3 /absolute/path/to/mnemos/scripts/mcp_server.py --data /absolute/path/to/private-data
codex mcp list
```

Use the actual Python 3.11+ executable if the client cannot resolve `python3`. Configure this in the environment that can access the private data directory. Codex supports local stdio server commands and arguments; hosted ChatGPT does not read local Codex configuration files. [Official MCP configuration guidance](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

Copy desired folders from `skills/` into the working project's `.agents/skills/`, preserving existing content. For example, the destination for capture is `.agents/skills/mnemos-capture/SKILL.md`. Project discovery is documented in the [official skills guide](https://learn.chatgpt.com/docs/build-skills).

## Claude Desktop local connection

The [Claude Desktop installer](claude-desktop.md) performs a real connector preflight, merges the entry below, and preserves a backup of existing settings. Use `python3 scripts/install_claude_desktop.py --data ./data --apply`, then fully restart Claude Desktop.

In the client's developer MCP configuration, merge this named entry with existing servers. Replace every illustrative path with an absolute path on your machine:

```json
{
  "mcpServers": {
    "mnemos": {
      "command": "python3",
      "args": [
        "/absolute/path/to/mnemos/scripts/mcp_server.py",
        "--data",
        "/absolute/path/to/private-data"
      ]
    }
  }
}
```

Use the absolute Python executable when needed, and JSON-escape Windows backslashes. Restart the client after saving and confirm the Mnemos tools are available. The official MCP guide describes the `mcpServers`, `command`, and `args` configuration pattern and local-server troubleshooting. [Local MCP connection guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers)

Only register a data directory the assistant should be able to read and contribute to. The local process can read the library, and its capture tool can save drafts. This setup does not modify the client's other server entries or install skills into other applications automatically.

## Available tools

| Tool | Input | Result |
| --- | --- | --- |
| `search_documents` | `query` | Matching documents with current revisions |
| `read_document` | `id` | Current document content and metadata |
| `capture_document` | `document` | Saved draft; existing IDs need their current revision |
| `recall_context` | `query`, optional `budget` | Bounded source excerpts and provenance |
| `plan_workflow` | `id` | Validated dependency order; no execution |

The local MCP interface implements tool discovery and tool calls over stdio. It is a deliberately small integration; it is not a remote OAuth service or a claim of certification across every MCP client version. Test discovery, a read, and a disposable draft capture in your intended client before relying on it for ongoing work.

Recall accepts a character budget, clamped to 500–24,000 characters. It returns `context`, `items`, `characters`, `estimated_tokens`, and a keyword retrieval method label. Each selected item identifies its source document and revision. The estimate uses approximately four characters per token and is not a model-specific tokenizer result.

## Cloud chat without a local connection

Use [Cloud handoff](cloud-handoff.md) to download a bounded context pack, optionally select full source documents, and provide the chosen files to a cloud chat yourself. Supply `mnemos-handoff` to obtain one **new draft** capture JSON. Import that JSON, or paste it using **Paste JSON instead**, in Capture knowledge, inspect its preview and source links, and save it locally. The portal's file import does not update existing notes.

Source IDs and revisions preserve provenance; `related_ids` lets Mnemos add links to existing Obsidian notes. A useful handoff states goals, current state, constraints, decisions, failed approaches, unknowns, next actions, and evidence. It excludes secrets and does not claim to summarize inaccessible older chats. Uploads still follow your organization's data policies.

For environments that explicitly want an ongoing cloud connection, the separately configured [Secure MCP Tunnel](chatgpt-tunnel.md) and [hosted GPT Actions](cloud-chatgpt.md) routes remain optional. Selecting a setup mode or installing a skill does not create or verify either connection. Existing tunnel profiles and credentials are not altered by the Mnemos rename. A public authenticated remote MCP connector for browser-based Claude remains future work.
