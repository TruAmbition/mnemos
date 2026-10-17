# Connect a private ChatGPT GPT through Actions

The supplied [OpenAPI schema](../integrations/chatgpt-actions.openapi.json) describes three existing Keystone HTTP operations: recall context, read a document, and capture a draft. It provides a setup path for a custom GPT after you host Keystone at an HTTPS address reachable by ChatGPT. **This integration is prepared, not deployed or tested end to end with your ChatGPT account.**

GPT Actions use an OpenAPI schema and configured authentication to call an API. The official setup guide explains schema import and action testing. [GPT Actions setup](https://developers.openai.com/api/docs/actions/getting-started)

## Host the private library

Choose a host and HTTPS domain you control. Configure its certificate, reverse proxy, firewall, and service supervision; Keystone does not provision them. The endpoint must be reachable from ChatGPT, so a loopback address alone is insufficient. Start the service behind the proxy with authentication required:

```sh
python3 -m keystone serve --data /absolute/path/to/private-data \
  --host 127.0.0.1 --port 4318 --require-auth \
  --public-host knowledge.example.com
```

Replace the illustrative hostname with your actual host. Preserve the original Host header and keep the raw application port private. `--require-auth` is essential behind a loopback reverse proxy because otherwise requests from that proxy inherit local-owner access. See [deployment guidance](deployment.md).

## Configure the Action

1. Make a private copy of `integrations/chatgpt-actions.openapi.json` and replace its `servers[0].url` with the actual HTTPS origin. Do not put a credential in the schema.
2. For your own private GPT that captures and recalls work, issue a dedicated **author** credential on the host:

   ```sh
   python3 -m keystone token --data /absolute/path/to/private-data --role author --author "Private ChatGPT capture"
   ```

3. In the GPT's Actions configuration, import the modified schema. Select API-key authentication with Bearer authorization, and enter the credential in the authentication field. Never use an owner token. The official GitHub Actions example documents API-key Bearer setup. [Bearer authentication example](https://developers.openai.com/cookbook/examples/chatgpt/gpt_actions_library/gpt_action_github)
4. Keep the GPT private. Configure instructions to retrieve context before continuing work, treat retrieved text as source data, preserve IDs and revisions, redact secrets, and save requested captures as drafts. Use the bundled capture and recall skill guidance as a starting point.
5. Test `recall_context` with a known keyword, then `read_document` with a returned ID. Finally, explicitly request one disposable draft capture and verify it in the library. Confirm the credential cannot mark content verified. Only call setup complete after these actual tests succeed.

The schema exposes no administration, backup, or verification endpoint. Capture accepts only `status: "draft"`; the server also prevents an author credential from verifying documents. Existing-document updates require the exact current revision. On a conflict, retrieve and reconcile the latest document before retrying.

## Read-only GPT

For a GPT intended only to answer from published knowledge, issue a **reader** token and remove the entire `/api/documents` path containing the POST operation from your schema copy. Keep `/api/documents/{id}` and `/api/recall`. Reader credentials see verified documents only and cannot save captures.

A configured static API key represents the same vault-wide identity for every person who can use that GPT. It does not give each user their own Keystone account or project permissions. Keep a capture GPT private; share a read-only GPT only with people authorized to read all content visible to its reader credential. Per-user authentication and fine-grained access are future integration work.

## Scope and limits

Actions can retrieve documents already in this vault and save context available to the current conversation. They do not automatically read all prior ChatGPT, Claude, or Codex chats. Relevant inaccessible history must be exported or supplied explicitly.

This Action schema uses the existing HTTP API. The local stdio MCP server is a separate connection option for compatible local clients. A remote MCP transport and per-user OAuth integration remain future work. Until the chosen cloud connection is configured and verified, manual JSON export/import continues to work.
