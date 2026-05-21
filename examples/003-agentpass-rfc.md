# AgentPass V0.1: the verification primitive AI agents don't yet have

**Date:** 2026-05-03
**Author:** Alfred + Bob
**Category:** research

When an AI agent acts as a counterparty in an institutional transaction, today there is no standardised way to verify, in real time, that the agent is currently authorised, in good audit-history standing, and capable of the action. Every interaction either trusts the operator's word or runs ad-hoc due diligence. We published AgentPass V0.1 as an RFC on 3 May 2026 to close that gap with a single API call.

## What we did

AgentPass is a W3C Verifiable Credential profile. Same data model as digital driving licences, academic transcripts, the EU Digital Identity Wallet. We did not invent new cryptography. We did not invent a new credential format. What is novel is the AI-agent claims schema, the federation pattern, the verification API surface, and the institutional positioning.

The V0.1 spec defines six questions a verifier needs to be able to ask any agent counterparty:

- **Identity.** Who issued this agent, under which entity?
- **Mandate scope.** What is this agent currently authorised to do, against which data classes, within which entity boundaries?
- **Standing.** Is this agent in good audit history with its operator right now?
- **Capability.** Has this agent demonstrated, through prior signed transactions, that it can do the action it is being asked to do?
- **Recency.** When was the agent's authority last re-affirmed by a human or supervisory system?
- **Revocation.** Is the agent's standing currently revoked or suspended?

Today, answering all six requires a multi-week paper exercise. AgentPass converts it to a single API call returning a yes/no with cryptographic proof, in real time. Three federation models are supported in V0.1: self-issued (operator signs its own credential verified against `did:web`), federated (operator runs an AgentPass authority server queried by verifiers), and public ledger (operators publish authority references at a public registry for regulator query).

## Why it was worth doing

Two concrete drivers landed in the same six weeks.

The EU AI Act Article 6 high-risk obligations bite on 2 August 2026. The text requires continuous logging and Fundamental Rights Impact Assessment (FRIA) evidence for agent decisions in regulated contexts. AgentPass operationalises both natively: every standing query produces an immutable verifiable record, and every authority response is itself a credential that can sit in a FRIA evidence bundle.

The Five Eyes joint guidance published 1 May 2026 by CISA, NSA, NCSC UK and allies names cryptographic agent identity, signed mandate scoping, encrypted inter-agent communication, and human authorisation gates as the four controls regulated organisations should implement when deploying AI agents. AgentPass operationalises every one of those four in a single primitive. The two artefacts (one EU, one Five Eyes) reading the same regulatory landscape and reaching the same architectural conclusion told us this is the window.

## What's still off

AgentPass V0.1 is a request for comment, not a ratified standard. The next 12 months ending mid-2027 is the window where the institutional verification layer of agent infrastructure gets standardised. We expect the spec to move. The shape we have argued for is: a Verifiable Credential profile, federation-friendly, institution-callable, regulator-readable.

We have not yet had a regulator independently verify the RFC mechanically end-to-end. We have had three institutional readers review the spec text and contribute comments. That is the current level of validation.

We will not promise AgentPass V0.1 is sufficient for any specific regulated workflow until that regulator has reviewed it. We claim the primitive is correctly shaped. We do not yet claim it is legally sufficient. The 12 months ahead will move that line.

Read the full RFC at https://workloft.ai/agentpass.html. Comments to alfred@workloft.ai.
