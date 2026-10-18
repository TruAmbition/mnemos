# Documentation backups with a Git remote

Open **Manage → Backups & settings → Git remote**. The native desktop also shows this status under **Backups**, with a button to open configuration.

This is separate from Projects: engineering checkouts supply context; this dedicated repository stores documentation backups. Mnemos remains usable without Git. Existing local and cloud ZIP backup settings stay independent.

## Status light

| Light | Meaning | Next step |
| --- | --- | --- |
| Red | No documentation Git repository is configured, or a backup operation needs attention. | Choose local-only use, configure Git, or read the error beside the light. |
| Amber | A local Git repository exists, but current documentation is not confirmed on the remote. | Commit locally, add a remote, or push pending changes. |
| Green | Current documentation matches the last successful push to the configured remote. | No pending documentation backup detected. |

The label and last commit/push times explain the status without relying on color. The web settings page refreshes status every 30 seconds. Green is confirmation of the last push, not a live availability check of the hosting service. A remote URL alone is never green. New documentation changes turn it amber; failed operations turn it red.

## Configure once

1. Enable documentation Git backup.
2. Choose an **existing dedicated repository** or **create inside a parent folder**. Existing repositories must be empty or previously managed by Mnemos for this workspace. Mnemos refuses application repos, unrelated files, manual changes, symlinks, submodules, and linked worktrees. For creation, choose an existing absolute parent path and a new child directory name, such as `mnemos-docs`. Nothing is created at a default home location without that selection.
3. Optionally enter a **Git remote URL**, using HTTPS or SSH. Create the remote repository with your Git hosting service first; use a private repository for private engineering work. Mnemos cannot verify a host's visibility/access policy. It uses the existing Git login or SSH setup, never asks for a token in this form, and does not create a GitHub repository. Saving sets the dedicated checkout's `origin`; an unexpected separate push URL is rejected.
4. Select **Automatically commit documentation changes locally** to check every five minutes while the local service runs. No changes means no extra commit. Closing the browser is fine; stopping Mnemos pauses checks.
5. Select **Automatically push** if desired. This also enables automatic commits, and requires a remote plus the explicit full-history acknowledgement. Manual **Commit locally now** and **Back up & push now** buttons remain available.
6. Save the settings. Saving does not upload anything. Run a backup to confirm your configuration. Git authentication must already work without an interactive prompt; SSH host verification remains enabled.

Disable the option to stop future automation. Existing local and remote history remains. Changing the destination resets the successful-push status until that destination is backed up. Only one Git backup destination is active per documentation workspace; switching workspaces uses that workspace's own configuration.

## Files and privacy

The checkout contains `vault/` with ordinary Markdown, maps, workflow files, attachments within the size limits, and project/privacy definitions. `.mnemos-backup.json` records file hashes and backup provenance. The workspace identity is a hash of the local data path, not its literal path.

Installation configuration, runtime keys, AI approval records, personal `.obsidian` settings, `.env` files, Git attributes/modules/ignore files, caches, and trash are excluded. Project notes and definitions can still contain internal service names, local paths, or confidential context: review them before remote sharing. Local backups are plaintext and may include private notes.

**Remote pushes obey Mnemos sharing policy.** All documentation must permit team sharing and pass the full-export checks and common-secret screening. A private Git remote is still external storage. History created while content was local-only cannot subsequently be pushed by Mnemos: keep that repository locally and create a fresh dedicated repository after classifying the intended content. History containing removed/unclassified files also blocks remote push. Screening checks all historical file contents, not only the latest version. These conservative restrictions prevent an earlier private snapshot from being uploaded accidentally. They do not delete copies already pushed or stop a user from running Git directly outside Mnemos.

## Reliability and boundaries

- Backups use the `mnemos-backup` branch and fixed Mnemos author identity. Global Git name/email setup is not required.
- Local commits are retained after a failed push. Automation retries on a later check; the UI records the failure.
- Mnemos does not pull, merge, force-push, push other branches/tags, or run repository hooks or content filters. A divergent remote requires deliberate Git resolution or a fresh destination. Keep the backup branch reserved for Mnemos.
- Other repo files and uncommitted manual edits cause a stop rather than being overwritten. The live vault remains the source of truth. If interrupted while updating a backup checkout, recover its committed tree into a new checkout; do not delete your original vault.
- Limits: 25 MB per file, 250 MB per snapshot, 10,000 files, and at most 1,000 commits / 250 MB of distinct file history when screening a remote upload. Use snapshot backups for large libraries or attachments. Unknown binary attachments are not allowed in remote exports.
- A local Git repo on the same disk does not protect against losing the workstation. A remote backup still depends on the host's availability, permissions, and retention. Mnemos does not encrypt the repository or promise a backup while its service is stopped.

## Recover on another computer

Clone the backup repository and select the `mnemos-backup` branch. Initialize a new Mnemos workspace, stop its service, preserve/remove its starter vault, and copy the backed-up `vault/` into the now-empty destination. Start Mnemos and verify the library. Reconfigure assistant connections, source checkout paths, and backup settings; review the recovered privacy policies. AI approvals and credentials are deliberately not restored. Configure a fresh dedicated Git backup repository for the new workspace path. Never overwrite a live vault during recovery.
