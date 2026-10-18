# Privacy and sharing

Mnemos 0.10 defaults to **Local only**, including existing projects and notes with no project. Upgrading does not automatically grant new access or approve old notes. Existing plain Markdown files stay on disk; a local owner can still read, search, edit, map, and back them up.

## Choose a policy

Open **Projects → Edit project → Project privacy**, or **Privacy & sharing** in the Manage navigation. The Swift desktop Projects screen shows each policy and opens these controls.

| Setting | Local work and local backups | Connected AI / handoffs / generated skill exports | Shared workspace |
| --- | --- | --- | --- |
| Local only | Allowed | Blocked | Blocked |
| Allow reviewed AI sharing | Allowed | Only explicitly approved note versions | Blocked |
| Approved for team sharing | Allowed | Still requires note-version approval | Allowed by workspace role; readers see verified notes only |

Nothing is uploaded or published by choosing a policy. “Team” is a content classification, not a public link or a list of individual project members. Workspace credentials still determine owner, author, and reader roles. Different per-project membership lists are not implemented.

Use **Privacy & sharing → Review sharing** to read a note's full record and metadata. For an unassigned note, select its policy here. Select the review checkbox and **Approve this version for AI** to allow assistant reads and exports. Approval persists until revoked or invalidated; it is not a one-time upload. Connected AI clients may read approved notes without another prompt on every request.

Approval is tied to the note's revision, transitive sources, project definitions, captured repository state, and privacy records. Changes require another review. **Revoke AI approval** blocks future Mnemos reads and exports. It cannot delete copies already shared.

## Shared repositories and combined workflows

A repository can belong to several projects. Its notes inherit the strictest project policy. Derived notes follow recorded source references, related-note links, and recognized Obsidian file links. Missing source records and missing historical projects fail closed to Local only. Cycles do not bypass checks.

Removing a project grouping or changing a note's visible source links does not erase historical privacy associations. To change a deleted project's policy, restore its original definition/ID from a trusted local backup. This conservative behavior prevents disconnecting a private repository from declassifying its existing snapshots. Mnemos cannot infer undocumented semantic dependencies; preserve source citations when importing AI work.

## What is enforced

- MCP searches, reads, recalls, and workflow plans expose only currently approved AI content. MCP capture returns a receipt, not source content; a newly captured draft needs local review before recall.
- HTTP credentials have an `ai` or `team` audience. Existing credentials default to `ai`. The local launcher credential is separate from shared credentials. A shared owner token cannot manage privacy, repositories, local settings, backups, or generated export artifacts.
- AI handoffs, cross-document analysis, project explanation packs, generated skill previews, and later downloads recheck current sources. Cached copy/download actions compare the reviewed fingerprints again. Local search remains unrestricted for the authenticated local owner.
- Static readers include only team-approved, verified notes and fully eligible workflows. Full-vault exports and cloud backups require team classification throughout and reject unclassified attachments/extra files. Use local backups to preserve restricted material.
- Repository refresh only reads local Git history and saves local context. It does not make model calls or upload context.

For a shared reader, create a credential locally with `python -m mnemos token --data /absolute/data --role reader --author "Reader name" --audience team`. Keep its output private. The default token audience is `ai`, which requires explicit note approvals. Do not give a `team` credential to an AI client: it is a human-team sharing credential and grants the team access described above. Network sharing still requires the documented host allowlist, authentication, and a TLS reverse proxy.

## Local sign-in

Launch Mnemos normally. A private random credential is stored in a `.mnemos-access` directory beside the installation data folder, outside the vault and its backups. On POSIX systems the directory is mode 0700 and key files are mode 0600. Windows relies on the current user's directory ACLs; Mnemos does not install an independent Windows security boundary.

The native manager reads that credential. A browser launch briefly carries it in a URL fragment, removes the fragment, and exchanges it for an HttpOnly, SameSite session. It is never printed, placed in a URL query, or sent in request logs. Restarting the service rotates the credential; browser sessions expire after 12 hours. Open from the launcher again if a direct bookmark asks you to sign in. There is no localhost owner fallback.

Restart all older Mnemos web, native, MCP, and tunnel processes after upgrading. An already running older process does not load new policy enforcement automatically. Reconnect assistant clients to the updated runtime.

## Boundaries and remaining risks

These controls govern Mnemos's APIs and export tools, not the operating system. An assistant, plugin, user, or malware with direct filesystem access under your OS account can read the underlying Markdown. Do not grant direct vault filesystem access to an assistant that must be restricted by Mnemos policies; use the constrained MCP connection instead.

Notes, privacy records, maps, and local ZIP backups are not encrypted by Mnemos. Protect the workstation and backup destination. A “local” destination inside a third-party sync folder may upload files outside Mnemos's control. Cloud encryption depends on your configured remote; it is not supplied automatically.

Secret screening checks common tokens, private-key headers, credential assignments, and all strings/metadata in outgoing records. It is best effort, can produce false positives, and does not recognize every secret or confidential business fact. Review before approval; redact at the source. Mnemos does not add an override to bypass a detected credential.

Disconnecting repositories or removing project groupings preserves notes, generated artifacts, and backup history. It does not revoke external copies or inherit GitHub organization permissions. Removing GitHub access will not erase captured documentation. The reconstruction prompt and release packages must contain source and synthetic fixtures only; private runtime keys, vaults, and approval records are excluded.

## Git documentation backups

Optional documentation Git backups preserve local history without changing project checkouts. Local snapshots may include private content. Remote pushes are external full-vault sharing and require the applicable team classification and secret checks, including historical contents. A snapshot captured while sharing was blocked remains local-only in that repository. Saving a remote URL never uploads content. See [Git documentation backup settings and recovery](git-documentation-backup.md).
