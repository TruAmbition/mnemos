# Optional direct ChatGPT connection

This is an optional connection for direct ChatGPT access to Mnemos. The product rename leaves existing runtime keys, tunnel ownership, and stable `keystone` profile/receipt files unchanged.

## Is a tunnel worth it?

**Start with local tools.** Choose a tunnel when you frequently want authorized ChatGPT reads and writes against current notes. Choose file handoff when you want explicit source selection for each cloud task and policy allows those uploads.

| Route | What you gain | What you manage |
| --- | --- | --- |
| Local Codex or Claude client | Direct lookup and draft capture without a tunnel. | A configured, authorized local client. Its model may still process selected context in the cloud under that client's policies. |
| Cloud file handoff | You choose the sources to share; no persistent connection. | Export, upload, review, and import a new draft. The exported snapshot can become stale. |
| Direct ChatGPT tunnel | Current-note lookup and direct draft creation or updates with revision checks; no manual file transfers. | An online, awake host, running tunnel client, internet access, runtime credential upkeep, and explicit approvals for note versions. |

OpenAI's client forwards requests and responses over outbound HTTPS; the private MCP server needs no inbound public port. Account/workspace access and enterprise outbound-connection policies still apply. [Official tunnel architecture and access requirements](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)

**Mnemos 0.10 exposes only note versions approved for AI sharing.** Local only content is blocked. Use Privacy & sharing to review, approve, or revoke notes, including drafts. Requested approved content reaches the cloud chat; capture returns a local save receipt. Restart older tunnel/MCP processes after upgrading. See [Privacy and sharing](privacy-and-sharing.md).

A tunnel adds no automatic backup, vault synchronization, workflow execution, or access to other chats. This ChatGPT setup does not connect every Claude mode. It also promises no token savings: retrieved text still consumes context.

Changing the setup preference does not enable or disable an existing tunnel. Stopping its client prevents future calls through that local connection; it does not remove content already shared in a chat.

OpenAI requires a Platform tunnel associated with the intended ChatGPT workspace, a runtime key with Tunnels Read + Use, and permission to add a custom MCP server. Creating a tunnel needs Tunnels Read + Manage. These account permissions are separate. See the [official Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

In Platform's Runtime API keys page, create a **Restricted** key with **Tunnels: Read + Use**. The key's account must also have those permissions for the selected tunnel. Keep the runtime key separate from any admin key. See the vendor's [permission setup](https://github.com/openai/tunnel-client/blob/master/docs/permissions.md#creating-keys).

## Prepare the local connection

Download the matching executable from the official [OpenAI tunnel-client latest release](https://github.com/openai/tunnel-client/releases/latest), verify its release checksum, and extract it. The helper was validated against version 0.0.16 on macOS. Windows and Linux connection behavior has not been exercised here. The bundled tests do not require a live OpenAI account.

In a terminal in this Mnemos project, run the following with your actual binary path and tunnel ID. IDs are not API keys.

```sh
python3 scripts/connect_chatgpt.py prepare \
  --binary /absolute/path/to/tunnel-client \
  --tunnel-id tunnel_REPLACE_WITH_THE_ID_FROM_PLATFORM
```

This uses the workspace selected in setup, runs a local, read-only MCP discovery check, and writes an isolated profile into that workspace's `connections/chatgpt` folder. It creates no tunnel, adds no ChatGPT plugin, makes no external connection, and stores no credential. Existing different or edited profiles are preserved with an error. Add `--data /absolute/path/to/mnemos-data` to pin every command to the workspace whose connection you intend to manage.

Prepared profiles contain an explicit vault path. Changing the active default does not retarget an existing or running tunnel. Commands without `--data` inspect only the newly selected workspace; they fail if it has no intact prepared profile. To manage an older connection, use its explicit data path. Do not prepare a replacement against another library merely to clear that error.

For the simplest Mac startup, put the verified executable at `tools/tunnel-client` inside the selected workspace, then double-click **start-chatgpt.command**. It opens Terminal, asks for the runtime key once through hidden input, checks connectivity, and keeps the tunnel running. The executable is private runtime data and is not included in the toolkit's source export. Alternatively, install the client on your PATH or point `MNEMOS_TUNNEL_CLIENT` at its location.

The equivalent one-prompt terminal command is:

```sh
python3 scripts/connect_chatgpt.py connect --binary /absolute/path/to/tunnel-client
```

To validate connectivity separately:

```sh
python3 scripts/connect_chatgpt.py doctor --binary /absolute/path/to/tunnel-client
```

The helper asks for the restricted runtime key through hidden terminal input. It passes the key only in the child process environment, redacts it from forwarded output, and never writes it to a profile, command line, or shell history. A secret manager can instead provide `MNEMOS_TUNNEL_API_KEY` in the environment. Do not paste the key into chat, a command argument, a note, or an `.env` file.

After those separate checks pass, start the connection in a terminal you will keep open:

```sh
python3 scripts/connect_chatgpt.py run --binary /absolute/path/to/tunnel-client
```

In a second terminal, check readiness:

```sh
python3 scripts/connect_chatgpt.py status
```

Both `healthy` and `ready` must be true before proceeding. The helper uses an automatically selected loopback port for the client's health interface. Press Control-C in the running terminal to disconnect. After a reboot, start it again. This helper deliberately does not register a background service or persist the runtime key.

## Finish in ChatGPT

In ChatGPT's Plugins settings, add a custom MCP server named **Mnemos**, choose **Tunnel**, and select the same tunnel. Use no additional MCP authentication for this personal stdio connection; access depends on the tunnel's workspace and account permissions. Keep this plugin private. The process exposes the selected vault to every account allowed to use this connection; use a separate vault if you need a different audience.

Attach Mnemos to a chat, then test a read:

> Recall relevant Mnemos context about the Mnemos implementation. Show the source IDs and verification status.

Confirm that the response came from a successful `recall_context` tool call, rather than the assistant's memory. Next test a clearly labeled draft:

> Export this short connection test to Mnemos as a context note titled “ChatGPT connection test”. Record that this is a connectivity check, not production documentation.

Verify the returned document in Mnemos or Obsidian. Setup is complete only after an actual ChatGPT tool call succeeds. Local profile creation or a healthy tunnel alone does not establish that ChatGPT is connected.

## Everyday use

If the Mac launcher reports `Operation not permitted` while opening a file inside Documents, macOS may be blocking the launching app's access to that folder. Finder's **Get Info → Open with** shows which app opens the launcher; it normally uses Apple's Terminal. In **System Settings → Privacy & Security → Files and Folders**, review that app's **Documents Folder** permission, allow it if appropriate, close the failed launcher window, and reopen the launcher. Terminal and iTerm have separate permissions. This is an operating-system permission, not a bad runtime key. See [Apple's file-access guidance](https://support.apple.com/guide/mac-help/control-access-to-files-and-folders-on-mac-mchld5a35146/mac).

- “Export context to Mnemos. Preserve decisions, current state, evidence, failures, unresolved questions, and the next action. Exclude secrets.”
- “Recall relevant Mnemos context for [project or problem] before doing fresh analysis.”
- “Find my previous runbook for [task], read it, and report whether it is verified.”

Mnemos tools cannot silently obtain other conversations or history that is unavailable to the assistant. Export the useful context from the current chat; recall retrieves only the saved material. Retrieval is keyword-based and uses a character budget to bound the returned context.

For vendor diagnostics and supervised runtime options, see OpenAI's [tunnel-client onboarding](https://github.com/openai/tunnel-client/blob/master/docs/onboarding.md). Do not report a managed runtime connected until its status confirms it is running and healthy.
