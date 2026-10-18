---
id: "example-server-access"
title: "Diagnose reader access problems"
type: "troubleshooting"
status: "verified"
project: "Mnemos example"
tags: ["mnemos", "reader", "access", "troubleshooting"]
author: "Mnemos examples"
updated: "2026-10-17"
verified: "2026-10-17"
summary: "Distinguish a stopped server, authentication failure, and unavailable documents."
example: true
---

# Diagnose reader access problems

> Example; verify in your environment. These are diagnostic checks, not a claim that an outage occurred.

## Symptom: the page will not open

1. Confirm the server process is running and note its reported address and port.
2. On the server machine, try the default local address: `http://127.0.0.1:4318`.
3. Confirm the intended data directory was supplied when starting the server. A different directory can expose a different library or fail initialization checks.
4. If local access works but another computer cannot connect, check the bind address and the private network or reverse proxy. The default loopback address is reachable only from the host itself.

Expected result: the local owner library, or a reader sign-in screen when authentication is required. Never solve a network problem by removing authentication.

## Symptom: the token is rejected

Check that the full token was copied without spaces, belongs to this installation, and has not been revoked or replaced. Use a reader token for reading; an author token is needed to write through an authenticated author interface. After recovery into a new installation, use its newly issued credentials.

A token is a credential. Do not include it in issue screenshots, a URL, a knowledge item, or an assistant transcript that will be shared.

## Symptom: a known document cannot be found

- Clear filters and search by a distinctive title word.
- Verify the note lives inside this installation's vault and outside the Templates directory.
- Inspect required frontmatter fields and ensure the `type` and `status` values are supported.
- Check whether the document is still marked draft or example and whether the current filters hide those documents. Reader credentials only expose verified documents.
- Confirm the file was saved in Obsidian, then refresh the reader.

Expected result: the document appears with the correct title, type, and status. The filename alone is not proof the metadata is valid.

## Stop condition

If startup fails because the port is already in use, stop or reconfigure the intended process or choose another available port. Do not terminate an unidentified process. If remote access requires a network or identity configuration you do not control, involve its owner with the non-secret error details.

## Evidence to collect

The exact error text, the local versus remote behavior, the selected data directory, and the attempted time. Redact tokens, personal file paths, and confidential document titles before sharing diagnostics outside the team.
