---
id: "example-mnemos-overview"
title: "How Mnemos keeps engineering knowledge"
type: "knowledge"
status: "verified"
project: "Mnemos example"
tags: ["mnemos", "architecture", "getting-started"]
author: "Mnemos examples"
updated: "2026-10-17"
verified: "2026-10-17"
summary: "One private Markdown vault powers Obsidian and the searchable reader."
example: true
---

# How Mnemos keeps engineering knowledge

> Example; verify in your environment. This page describes the toolkit, not a completed engineering incident.

## Purpose

Keep explanations, repeatable procedures, and evidence together so an engineer can recover the reasoning behind a change without rereading an entire conversation.

Mnemos uses a dedicated Markdown vault. Obsidian opens that vault for editing, and the web reader presents the same files as searchable documentation. The toolkit source can be shared on GitHub while each installation keeps its private vault and access tokens separate.

## What goes where

| Content | Document type | Useful outcome |
| --- | --- | --- |
| Repeatable procedure | Runbook | Someone can perform and verify the task. |
| Reusable explanation | Knowledge item | Someone understands the behavior and where it applies. |
| Diagnosis and resolution | Troubleshooting | Someone can recognize the symptom and narrow the cause. |
| Implementation rationale | Decision | Someone understands alternatives and tradeoffs. |
| Session evidence | Work log | Someone can trace what actually happened. |
| Small bounded action | Microtask | An assistant can plan one action with clear success and stop conditions. |
| Session handoff | Context | Another assistant can resume from known state and source references. |

## Current boundaries

The bundled skills guide an assistant that already has access to the relevant work. They do not automatically collect other chats, log into cloud sessions, or run every documented command. No model API key is required for the local application.

The current search and bounded context recall use text and metadata. Local MCP tools connect compatible assistants. Semantic retrieval and an authenticated remote cloud connector are future extensions. Workflow planning checks dependencies and source documents; it does not execute commands.

## Private data and sharing

Use the toolkit repository for application code, templates, and examples. Keep real engineering documents in the private runtime directory. Reader tokens grant access to the library; they are not document-by-document permissions. Use a private network or an HTTPS reverse proxy for remote access.

Cloud backup copies an archive to a configured storage destination. It is separate from live multi-device vault synchronization. A local vault remains the working copy.

## Related documents

- [[Runbooks/first-capture|Capture a documented engineering task]]
- [[Runbooks/backup-recovery|Back up and recover a knowledge vault]]
- [[Troubleshooting/server-access|Diagnose reader access problems]]
