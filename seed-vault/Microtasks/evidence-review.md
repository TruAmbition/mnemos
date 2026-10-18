---
id: "example-evidence-review"
title: "Review evidence before documenting work"
type: "microtask"
status: "verified"
project: "Mnemos example"
tags: ["mnemos", "evidence", "microtask"]
author: "Mnemos examples"
updated: "2026-10-17"
verified: "2026-10-17"
summary: "Identify supported facts, unknowns, and sensitive material before drafting."
example: true
---

# Review evidence before documenting work

> Example; verify in your environment. This is a bounded documentation task, not an instruction to execute the source work.

## Purpose and scope

Review only the work and sources accessible for the current request. Build a concise evidence map that a documentation step can use.

## Inputs

- User's requested scope and intended audience.
- Accessible conversation, changes, command results, or linked artifacts.
- Project and environment, when known.

## Action

For each important claim, identify a supporting source and whether it was observed, tested, proposed, or remains unknown. Capture why a decision was made when the source explains it. Record unsuccessful approaches only when they help future diagnosis.

List any source material that was unavailable. Replace secrets with descriptive placeholders, preserving the operational meaning of a command without retaining credentials.

## Output

A compact evidence map: claim, supporting source, verification state, and outstanding question. Include likely existing documents to update after searching the library.

## Success check

Every claimed completed action has evidence. Every proposed or untested action is labeled. Missing access is visible, and secrets are absent.

## Stop conditions

Stop the dependent documentation step when it would require guessing a dangerous or essential command, undocumented prerequisite, or successful result. Ask for the missing evidence or save a clearly incomplete draft. Do not execute a production action merely to fill a documentation gap.

## Authorization and retry

This task authorizes reading relevant accessible sources and producing an evidence map. It does not authorize deployment, credential changes, or outreach. Recheck a failed source once when appropriate; persistent access failure becomes an explicit limitation.
