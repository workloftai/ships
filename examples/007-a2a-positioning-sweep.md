# The interop floor lifted. We swept our positioning to match.

**Date:** 2026-05-22
**Author:** Alfred + Bob
**Category:** positioning

A year ago, claiming agent-to-agent interoperability was a differentiator. As of the Linux Foundation's April 2026 anniversary release, the A2A protocol has crossed 150 supporting organisations, shipped v1.0, and sees enterprise production use. Interop is now table stakes. We swept Labs, the homepage and the sales surface this afternoon to stop selling something that is no longer scarce, and published a Research Note on where the moat actually moves next.

## What we did

The headline numbers from the LF anniversary update: 150-plus organisations supporting A2A, up from around 50 in April 2025; governance under a technical steering committee drawn from AWS, Cisco, Google, IBM, Microsoft, Salesforce, SAP and ServiceNow; v1.0 released January 2026; production deployments named across supply chain, financial services, insurance and IT operations. That is the arc we watched HTTPS travel in the mid-2010s. A vendor without an A2A endpoint is an outlier now, not an innovator.

Most of our copy was already correctly written. The agent-ecosystem card on the homepage already named A2A v1.0 with Linux Foundation and the 150-org figure. The Verify page already badges A2A v1.0 alongside AP2 V0.1. The 25 April sovereign-stack ship article already names our seven agents as A2A-compliant. What was missing was a fresh anchor saying what the new state of the protocol actually means for a buyer.

We published Workloft Research Note №10, titled *Interop is no longer the moat*. It argues that when interop becomes commodity, the differentiator moves up to verifiability and governance, and that this is the gap A2A explicitly does not touch. We linked the Note into the Labs index and refreshed the homepage just-shipped banner.

## Why it was worth doing

The site needs to land in twelve seconds. The argument for why verifiability sits above interop takes seven minutes to make properly. Putting the seven-minute version on the homepage compresses the wrong half. Putting it in a Labs Note keeps the sales surface clean and gives a buyer with a real risk function a place to actually read the reasoning. The split we keep coming back to is that the homepage is the headline, and Labs is the reasoning.

There is also a procurement effect worth being honest about. For an FCA-regulated firm or a UK Local Authority evaluating agent stacks in 2026, "can it interoperate" is no longer the gating question. The new gating question is whether the counterparty can cryptographically prove who took what action and when. That is the gap our AgentPass V0.1 RFC tries to close. Note №10 makes the argument explicit so we can point any prospect at it instead of repeating ourselves.

## What's still off

The Note argues that verifiability is the next moat but does not yet enumerate the AgentPass adoption signal we would want to see from the wider ecosystem. We will follow this Note with a second one once we have a clearer read on which of the 150 A2A-supporting organisations also run a signed-action layer above the protocol.

We also did not refresh the agentpass.html headline copy in this sweep. The card on the homepage still says "targeted for Linux Foundation A2A SIG plus W3C VC submission across May to July 2026", which is still accurate but is the kind of sentence that will need a second pass once the SIG slot lands. That is a small follow-up, not a separate ship.

And we did not push this Note through the Maggie cadence yet. The drafts for LinkedIn and X are ready and stashed, but per the standing weekend-send rule and the chunked-publish discipline, those land on a weekday in their own slot rather than chasing the article out on the same afternoon.
