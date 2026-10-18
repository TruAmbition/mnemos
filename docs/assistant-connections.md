# Assistant connections and context handoff

Keystone provides a local MCP server and a CLI. Both use the same dedicated vault. A local desktop connection does not automatically make the vault available to a separately hosted chat.

## Project setup for Codex and Claude Code

From the source checkout, run:

```sh
python3 scripts/install_agents.py --data ./data --client both
```

Choose `--client codex` or `--client claude` for one client. Add `--project /absolute/path/to/working-project` to configure another workspace. The installer writes only project-local Codex or Claude Code configuration and skill copies. It preserves unrelated MCP servers and refuses conflicting Keystone definitions. Reopen and trust the project in the client before checking tool discovery. This does not configure Claude Desktop; use its separate example below.

## Codex local connection

Add the local server with absolute paths, replacing the illustrative paths below:

```sh
codex mcp add keystone -- python3 /absolute/path/to/keystone/scripts/mcp_server.py --data /absolute/path/to/private-data
codex mcp list
```

Use the actual Python 3.11+ executable if the client cannot resolve `python3`. Configure this in the environment that can access the private data directory. Codex supports local stdio server commands and arguments; hosted ChatGPT does not read local Codex configuration files. [Official MCP configuration guidance](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

Copy desired folders from `skills/` into the working project's `.agents/skills/`, preserving existing content. For example, the destination for capture is `.agents/skills/keystone-capture/SKILL.md`. Project discovery is documented in the [official skills guide](https://learn.chatgpt.com/docs/build-skills).

## Claude Desktop local connection

The [Claude Desktop installer](claude-desktop.md) performs a real connector preflight, merges the entry below, and preserves a backup of existing settings. Use `python3 scripts/install_claude_desktop.py --data ./data --apply`, then fully restart Claude Desktop.

In the client's developer MCP configuration, merge this named entry with existing servers. Replace every illustrative path with an absolute path on your machine:

```json
{
  "mcpServers": {
    "keystone": {
      "command": "python3",
      "args": [
        "/absolute/path/to/keystone/scripts/mcp_server.py",
        "--data",
        "/absolute/path/to/private-data"
      ]
    }
  }
}
```

Use the absolute Python executable when needed, and JSON-escape Windows backslashes. Restart the client after saving and confirm the Keystone tools are available. The official MCP guide describes the `mcpServers`, `command`, and `args` configuration pattern and local-server troubleshooting. [Local MCP connection guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers)

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

ChatGPT can also reach this local stdio connector through [Secure MCP Tunnel](chatgpt-tunnel.md), subject to OpenAI account and workspace access. The tunnel client must remain running on the machine holding the vault. This is separate from a public remote MCP endpoint and does not connect Claude's web client.

Use a manual exchange when ChatGPT, Claude, or Codex cannot access the installation:

1. Ask the assistant to export the accessible task as a draft `context` document using the [capture JSON format](../skills/keystone-capture/references/capture-format.md).
2. Save the returned JSON privately and import it with `python3 -m keystone capture --data ./data --file /path/to/context.json`.
3. Before a new session, run `python3 -m keystone recall --data ./data "relevant project" --budget 6000` or use the reader's recall interface.
4. Provide that bounded context to the new assistant. Retrieve full source documents when the excerpts are insufficient.

A useful context document states the goal, current state, constraints, decisions and rationale, failed approaches, unknowns, next actions, and sources. It should distinguish observed results from inference and omit credentials. It should not claim to summarize inaccessible older chats.

For a private ChatGPT custom GPT, the alternative [Actions integration](cloud-chatgpt.md) can remove the manual step once you host the HTTP API over HTTPS, configure its dedicated credential, and verify the connection. This Actions route has not been tested end to end. A public authenticated remote MCP connector for browser-based Claude remains future work. Hosting the reader alone does not configure an assistant, and connecting one assistant does not connect every other assistant automatically.
