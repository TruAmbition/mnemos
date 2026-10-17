---
id: "example-context-handoff"
title: "Carry context between assistants"
type: "context"
status: "verified"
project: "Keystone example"
tags: ["keystone", "context", "handoff"]
author: "Keystone examples"
updated: "2026-10-17"
verified: "2026-10-17"
summary: "A compact handoff preserves decisions, current state, unknowns, and the next action."
example: true
sources: []
related_ids: ["example-keystone-overview", "example-first-capture"]
---

# Carry context between assistants

> Example; verify in your environment. This page explains the handoff format and is not a transcript of an actual engineering task.

## Goal

Resume engineering work in a different assistant without reconstructing decisions from memory or pasting an entire conversation.

## Current state

Keystone supports context notes in the same private Markdown vault as runbooks and knowledge items. A context note can be drafted in any assistant and imported with the capture command. A locally connected MCP client can search, read, recall, and capture using the toolkit's tools.

## Constraints

Only accessible evidence can be exported. A local tool connection does not grant access to all earlier conversations. Cloud chats need a separately configured accessible connection or a manual context export/import step.

Keep credentials and unnecessary personal information out of the handoff. Do not assume a future assistant has the same tools, working directory, permissions, or live infrastructure access.

## Decisions and rationale

Use a compact context document for state that helps continue a task. Put durable procedures in separate runbooks and reusable explanations in knowledge items, then link their document IDs. This keeps a handoff concise while allowing an assistant to read deeper sources when needed.

## Failed approaches

No engineering attempts are recorded in this example. In a real handoff, include only failures supported by evidence and explain what was learned.

## Unknowns

The target user's project, actual current task state, accessible source artifacts, and deployment environment are unknown in this example.

## Next action

Ask the assistant to export the current accessible task as a draft context note. Include the goal, verified progress, constraints, decisions, failures, unresolved questions, and next actions. Save it using capture, then use recall in the next session to retrieve relevant excerpts with document IDs and revisions.

## Verification boundary

Recall selects and excerpts existing documentation using keywords; it does not verify claims or generate new model conclusions. A character budget limits the returned context. The token estimate is approximate and varies by model and language.
