# Connect Claude Desktop to Mnemos

Claude Desktop can launch Mnemos's local connector and read or save your selected vault directly from a chat. The website does not have to be running, and no tunnel is required. Keep the Mnemos project and its data directory at the paths used during setup.

## Install the connection

Run these commands from the Mnemos project folder with the same Python 3.11+ interpreter used to run Mnemos:

```sh
python3 scripts/install_claude_desktop.py
python3 scripts/install_claude_desktop.py --apply
```

The first command checks the connection without changing Claude settings. The second saves it. The installer starts the real MCP process and checks its advertised tools before writing anything. It preserves unrelated settings and servers, creates a private timestamped backup beside an existing config, and refuses to replace a different connection already called `mnemos` or `keystone`. An equivalent legacy `keystone` entry is renamed to `mnemos` only with `--apply`; the preflight shows the pending migration without changing files. Client-specific settings on the matching entry and unrelated settings are preserved.

Without `--data`, the installer uses the workspace currently selected in Mnemos setup and pins its absolute path into Claude's configuration. Add `--data /absolute/path/to/private-data` to choose a particular authorized workspace instead. Later default-workspace changes do not retarget an installed Claude connection; a conflicting connection is left unchanged. See [workspace selection](assistant-connections.md#workspace-selection-and-pinned-connections).

It uses the standard config location on macOS and Windows. If your installation uses a different location, find it in Claude's Developer settings and pass `--config /absolute/path/to/claude_desktop_config.json`. Absolute paths for Python, the connector, and the vault are written into the configuration. The installer never quits or restarts Claude.

Fully quit and reopen Claude Desktop after installation. Open the **+** menu in a chat, then **Connectors**, and enable Mnemos. Its tools should include `recall_context`, `search_documents`, `read_document`, `capture_document`, and `plan_workflow`. Claude may request permission before calling them.

## Use it in a conversation

Ask:

> Export this context to Mnemos. Save a concise handoff with the goal, decisions and reasons, completed work, test evidence, open questions, and next steps. Exclude credentials. Search for an existing related note before creating a new one.

Or:

> Recall relevant Mnemos context for [project or problem] before continuing. Cite the saved sources and point out anything that is still unverified.

Captures are drafts until you review them in Mnemos. A capture can only include the context Claude has available in that conversation; it cannot recover discarded or inaccessible history. Recalling a compact bundle avoids re-pasting a full transcript, but the returned text still uses conversation tokens.

The local connector can read only note versions approved for AI sharing and can create draft documentation or update accessible drafts. Newly captured drafts require local approval before recall. Restart older connector processes after upgrading. Connect only your own intended vault. It supplies workflow plans without running their commands.

## Desktop, browser, and other Claude modes

This connection is for local **Claude Desktop chat**. It does not automatically connect **claude.ai**, **Cowork**, or **Claude Code**. Claude Code has its own project setup through `scripts/install_agents.py`.

For ordinary cloud use, the [file handoff workflow](cloud-handoff.md) carries only the context you select and returns a new reviewed draft, without a connector. Browser and account-level Claude connectors use a publicly reachable remote MCP service, with authentication configured separately. A local file path or `localhost` URL cannot be used for those cloud connections. Do not expose a local unauthenticated Mnemos server to make it reachable.

## Troubleshoot or remove

If the tools are absent, check Claude's Developer settings for connection status and fully restart the app. On macOS, connector logs are under `~/Library/Logs/Claude`; on Windows, under `%APPDATA%\\Claude\\logs`. The Mnemos process requires the configured Python interpreter and project/data paths to remain available.

To disconnect, remove only the `mnemos` entry from `mcpServers` in Claude's config and restart Claude. Keep other server entries and preferences. A backup is available beside the config, but restoring that whole file would also undo settings changed after installation.

## References

- [Official MCP guide: connect local servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers) — config locations, server launch format, restart, and troubleshooting.
- [Claude Help: local MCP servers](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop) — connector visibility and Desktop settings.
- [Claude Help: remote custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) — cloud network requirements and the distinction from local Desktop servers.
