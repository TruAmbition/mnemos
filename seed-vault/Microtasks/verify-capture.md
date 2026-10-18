---
id: "example-verify-capture"
title: "Verify a captured knowledge item"
type: "microtask"
status: "verified"
project: "Mnemos example"
tags: ["mnemos", "verification", "microtask"]
author: "Mnemos examples"
updated: "2026-10-17"
verified: "2026-10-17"
summary: "Check a saved document against evidence without inventing successful execution."
example: true
---

# Verify a captured knowledge item

> Example; verify in your environment. Content review alone does not prove that every procedure works.

## Purpose and scope

Check that a saved document is faithful to the available evidence and usable by its intended audience.

## Inputs

- Saved document ID and its current revision.
- Evidence map and accessible supporting sources.
- Scope of any authorized practical checks.

## Action

1. Open the current document and compare its claims with the evidence map.
2. Confirm the purpose, prerequisites, environment, steps, expected outcomes, and recovery guidance are present where relevant.
3. Verify that commands use placeholders for secrets and do not omit essential working directories or inputs.
4. Search for the document in the reader and inspect its rendering and metadata.
5. Perform only already authorized practical checks. Record exactly which checks ran, where, and their outcome.

## Output

A review result with corrections, observed checks, and unresolved items. Keep status draft when verification is incomplete. Use verified only when its stated scope has actually been verified, with an honest verification date and environment.

## Success check

The document can be located, its assertions match the evidence, and its verification status reflects the checks actually performed. A polished page is not a substitute for evidence.

## Stop conditions

If the revision changed since planning, reread the current content and update the plan. If verification would mutate an external system beyond current authorization, stop before that action and request the needed authorization with the concrete action explained.

## Recovery

Apply corrections through an update against the current revision. If another author edited the page, reconcile both changes rather than replacing their work. Do not automatically delete a document because its verification failed.
