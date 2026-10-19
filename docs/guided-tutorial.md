# Guided tutorial

Open **Guided tutorial** in the sidebar, use the invitation at the top of **Getting started**, or choose **Guided tutorial** from the macOS manager’s Overview. New browser users still land on Getting started; returning users still land on the Library. The tutorial is available whenever you want it and does not interrupt explicit document links.

Select **Start tutorial** for the full tour (about 20 minutes), **Continue tutorial** to return to your place, or expand a chapter and choose one lesson. Every lesson explains what the feature does, why it is useful, how to use it, and its practical limits. Click the sample choices to explore examples; the Library lesson includes a search input and the graph lesson changes its color key.

| Chapter | Coverage |
| --- | --- |
| Make yourself at home | Purpose, dedicated workspaces, Library search and filters |
| Document useful work | Note types, reading evidence, capture/import, session summaries |
| Connect your projects | Top-level projects, repository context and commit monitoring, knowledge brain |
| Work with your AI | Context recall, cited answers, sharing approval, file handoffs, local connections and optional tunnels |
| Make work repeatable | Skill candidates, cross-document discovery, existing-skill matching, building and orchestration |
| Keep knowledge trustworthy | Version history and restoration, documentation health and snoozing |
| Protect your knowledge | Documentation Git backups, snapshot scope, complete recovery, optional meaning search |
| Your everyday workflow | Browser/native/Obsidian roles, team access, a practical engineering routine |

**Next** records the current lesson as reviewed. **Back** revisits the previous lesson; jumping to another chapter does not mark skipped steps reviewed. After the last lesson, the tour returns to any unreviewed content. Once all 28 are reviewed, it shows completion. You can revisit any completed lesson without erasing progress, or choose **Replay from beginning** in the overview to reset this tutorial’s progress.

**Save place & leave** returns to the Library. A feature’s **Open** button leaves the sample lesson for the real screen and retains your place. The normal feature access rules continue to apply: owner and author operations are labeled for readers, and local-owner features are unavailable to remote owner sessions. The tutorial itself remains available in signed-out and portable-reader views.

## Storage and privacy

Examples use fictional Checkout platform material embedded in the application. The tutorial never reads note bodies, makes model calls, creates notes, starts connections, changes sharing approval, or changes backup configuration. The host application still performs its normal bootstrap when opening any page. Opening a real feature leaves the tutorial and returns to the usual application behavior.

Only lesson IDs, reviewed IDs, a started flag, and schema version are kept in browser local storage. The key is scoped by workspace ID, role, and reader-export mode. It is not an account-level completion record, and does not sync to other browsers, computers, or workspace backups. Reader exports without a workspace identity share their tutorial progress when hosted at the same origin and role. Clearing site data resets it. If storage is blocked, in-memory progress lasts until the page is reloaded or closed; the tutorial explains that limitation. Malformed saved progress is reset without affecting other settings.

No install, tunnel, API key, model download, or production task is required to complete the tour. Finishing a lesson records that it was reviewed; it does not certify that the user performed or validated the real operation.

## Maintenance

Content and progression live in `web/tutorial.js`, with scoped styles in `web/tutorial.css`. The app’s route, onboarding invitation, sidebar link, and native Overview link are the only integration points. The static reader and standalone runtime include both assets through the existing web-directory packaging. There are no new server endpoints or dependencies. Keep lesson IDs stable when revising wording so existing progress remains meaningful; use a new progress schema/storage key for a substantially changed tour.
