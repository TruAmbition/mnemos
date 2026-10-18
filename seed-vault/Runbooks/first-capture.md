---
id: "example-first-capture"
title: "Capture a documented engineering task"
type: "runbook"
status: "verified"
project: "Mnemos example"
tags: ["mnemos", "capture", "runbook"]
author: "Mnemos examples"
updated: "2026-10-17"
verified: "2026-10-17"
summary: "Turn accessible task evidence into a draft with context, steps, and verification."
example: true
---

# Capture a documented engineering task

> Example; verify in your environment. The procedure below is a starting point, not evidence that a particular feature was implemented.

## When to use this

Use after completing meaningful work that another engineer may need to repeat or diagnose. Useful evidence includes an accessible conversation, reviewed changes, command outputs, and test results.

## Prerequisites

- An initialized Mnemos data directory.
- Access to the source work and permission to document it.
- The project, target environment, and affected component identified.
- A working assistant with the bundled capture skill, or a manually prepared capture JSON file.

## Procedure

1. Identify the outcome and evidence. Record what changed, why, and which checks were actually performed. Keep untested suggestions distinct.
2. Search the existing library by the component, error message, and feature name. Update a matching document when its purpose is the same.
3. Select the smallest useful set of document types. A short fix may only need one troubleshooting guide.
4. Draft exact prerequisites and ordered steps. Explain expected results, verification, rollback or recovery, and known limitations where relevant.
5. Remove credentials, private keys, session tokens, and unnecessary personal information. Replace needed secret values with named placeholders.
6. Save the draft using the capture command. When updating, use the document's current revision so a concurrent edit is not silently replaced.
7. Read the saved page and compare it with the evidence. Mark it verified only after the procedure and its environment have actually been checked.

## Expected result

A searchable draft with a clear purpose, meaningful metadata, and traceable evidence. The web reader and Obsidian both read the saved Markdown. Drafts remain distinct from verified knowledge.

## Verification

Search for the title or an exact phrase, open the result, and inspect the steps and metadata. Check that unsupported claims, credentials, and missing prerequisites have not slipped into the page. See [[Microtasks/verify-capture|Verify a captured knowledge item]].

## Recovery

If capture reports a revision conflict, read the latest document and reconcile the new material with it. Do not bypass the conflict by supplying an empty revision or writing over the file. If a draft is wrong, correct it with evidence; do not mark it verified merely to complete the workflow.

## Evidence to retain

Source task or issue links, relevant repository revision, affected versions, and the actual checks performed. Do not paste an entire conversation into the knowledge base by default.
