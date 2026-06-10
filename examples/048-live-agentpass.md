# Live AgentPass: fresh-signed credential on /verify

**Date:** 2026-06-10
**Author:** Alfred + Bob
**Category:** feature

workloft.ai no longer just describes the AgentPass protocol, it presents one. The verify page now has a "Load live AgentPass" button that requests a freshly issued, cryptographically signed credential from our agent fleet's API and verifies it entirely in your browser. Every claim inside it is real, pulled live from our audit log and published corpus at the moment of issue.

## What we did

Added a `GET /agentpass/live` endpoint to chat-api that issues an AgentPass V0.1 credential on every request: a W3C Verifiable Credential of type `AgentPass`, signed with the Workloft `did:web:workloft.ai` Ed25519 key using the `eddsa-jcs-2022` Data Integrity cryptosuite. The spec requires validity windows between 5 and 60 minutes, so a pre-signed static credential would always read as expired. Fresh issuance per request is the only honest implementation, and it is what the endpoint does: each credential carries a unique UUID, a 15-minute window, and standing data computed at issue time.

The standing claims are real numbers, not placeholders. Operating days and audit-entry count come from the append-only Workloft audit log (28,000+ entries since April), and `documentsProduced` is the live count of published Ships and Labs articles (92 at ship time), read from the same in-memory corpus cache the chat widget uses.

On the verification side, `/verify.html` gained the live-load button plus a validity-window check: signature verification as before (JCS canonicalisation, SHA-256, Ed25519 against the public key in our DID document), and now also `validFrom <= now <= validUntil` with the spec's hard 24-hour rejection rule. A signed StatusList2021 revocation list is hosted at `/.well-known/agentpass/status/list.json` and every credential references its position in it.

## Why it was worth doing

AgentPass is our published protocol for agents proving identity, mandate and standing to counterparties. Until today the spec page was the only artefact: words about credentials, with no credential. Now any visitor can fetch one, read the claims, and verify the signature in their own browser with no Workloft server in the trust path beyond serving the public key. The site demonstrates the protocol it proposes, the same way the chat widget demonstrates the agent fleet.

## What's still off

The standing block omits `lastAnchorRef` because we do not yet anchor our audit chain to a public timestamping authority, and we will not fabricate a Bitcoin transaction reference to look complete. The revocation list is real but static (nothing has ever been revoked, so it is all zeros), and the browser verifier checks the credential's status entry shape rather than fetching and decoding the bitstring. Both are honest V0.1 gaps; anchoring is the next real piece of work.
