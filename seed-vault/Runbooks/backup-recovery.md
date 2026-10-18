---
id: "example-backup-recovery"
title: "Back up and recover a knowledge vault"
type: "runbook"
status: "verified"
project: "Mnemos example"
tags: ["mnemos", "backup", "recovery"]
author: "Mnemos examples"
updated: "2026-10-17"
verified: "2026-10-17"
summary: "Create recoverable vault archives and test restoration in a separate directory."
example: true
---

# Back up and recover a knowledge vault

> Example; verify in your environment. A successful archive is not proof that recovery has been tested.

## Purpose

Protect the private knowledge library independently of the public toolkit source. Choose a local archive destination or a configured rclone cloud remote during setup.

## Prerequisites

- The path to the initialized data directory.
- Enough storage for the archive.
- For cloud upload, rclone installed and a working remote configured under your account.
- A separate empty directory for a recovery test.

## Procedure

1. Finish current edits so the backup represents a coherent set of documents.
2. From the toolkit source directory, run `python3 scripts/backup.py --data ./data`, substituting your private data directory.
3. Confirm the reported archive exists and inspect the command's outcome. For cloud storage, confirm the upload completed; a local archive alone does not prove it reached the remote.
4. Record the archive name, destination, and time. Treat archive contents as private engineering data.
5. Initialize a separate recovery installation with `python3 -m mnemos init --data ./recovered-data --author "Your name"`. Rename its generated `vault` folder to `starter-vault`, preserving it. Restore with `python3 scripts/restore.py BACKUP.zip --to ./recovered-data/vault`. The restore verifies the archive and refuses to replace a nonempty folder. Start the reader using `python3 -m mnemos serve --data ./recovered-data`.
6. Search for several recent documents and open their content. Inspect a workflow and any linked source notes before declaring the recovery test successful.

## Expected result

A dated archive and a working recovered copy. The archive contains vault files, not the installation configuration or access tokens; issue fresh tokens in the recovery installation. Record the recovery test date and any limitations in a real work log for your installation.

## Important limits

A cloud backup is not live synchronization. The working vault stays local to the host. Do not point two active writers at a cloud folder and assume Mnemos coordinates their file operations.

Do not assume archives are encrypted. For encrypted cloud storage, configure an appropriate rclone crypt remote and manage its recovery information separately. A backup stored only on the same disk does not protect against loss of that disk.

## Recovery and follow-up

Keep the original installation available while validating recovery. Reconnect the intended backup destination and reissue reader or author credentials as needed; do not email a backup archive as a way to share reading access.

## Related documents

- [[Knowledge/mnemos-overview|How Mnemos keeps engineering knowledge]]
- [[Troubleshooting/server-access|Diagnose reader access problems]]
