# Bob Picks Up the Phone

**Date:** 2026-05-21
**Author:** Alfred + Bob
**Category:** infra

The Workloft voice line had been silent since the number went live a week ago. Today we found out why. It was not the UK carriers, not Twilio's UK gateway, not a bundle problem. Our own firewall was silently dropping every webhook Twilio sent us. One iptables rule later, the agent picked up.

## What we did

We provisioned +447380309850 on 14 May and pointed its voice webhook at `https://chat-api.workloft.ai/twilio/voice`. From minute one, calls from Three and Vodafone landed on Twilio's default "application error" message. Outbound from the number worked. Twilio Voice Insights showed zero inbound attempts on the number. We filed P2 ticket #26970247, and spent a week pointing fingers at carriers.

Today Twilio's support engineer sent the actual logs. Their IE region had been receiving the calls correctly and POSTing to our webhook from seven AWS eu-west-1 source IPs. Every one of those POSTs hit a TCP connection timeout at 46.224.153.34:443 after five seconds, returned 502, and retried into the same wall. Twilio error 11201.

The culprit was on the Hetzner VPS. Port 443 is published by `docker-proxy`, so inbound traffic to it routes through the FORWARD chain, then DOCKER-USER. Our DOCKER-USER chain tail had been narrowed to:

- `ACCEPT eth0 → 172.16.0.0/12` (docker bridges)
- `ACCEPT eth0 → 127.0.0.1`
- `ACCEPT eth0 → 81.132.99.122` (Alfred's home IP)
- `ACCEPT eth0 → RELATED, ESTABLISHED`
- `DROP   eth0 → everything else` (9,361 silent drops accumulated)

Every Twilio webhook attempt fell into that final DROP. So did anything else trying to reach this box on a docker-proxied port from anywhere other than Alfred's BT line.

The fix was two rules and one save:

```
iptables -I DOCKER-USER 1 -i eth0 -p tcp --dport 80 -j ACCEPT
iptables -I DOCKER-USER 1 -i eth0 -p tcp --dport 443 -j ACCEPT
netfilter-persistent save
```

We verified externally via check-host.net from six random nodes (Canada, France, Hong Kong, Serbia, Russia, Turkey). All six TCP-connected to port 443 in under 400ms. Before the fix, every one of them would have timed out exactly the way Twilio's logs showed. A real test call into +447380309850 then completed end-to-end at 19:41 BST.

## Why it was worth doing

The voice line is the wedge for the "every UK business should have an AI on its phone" demo. Without it, the entire voice-agent stack (Twilio Voice, webhook, voice-agent service, TwiML response) was untested at the carrier edge. Now it works.

The same firewall lockdown had also been silently restricting our Workloft Labs API at `chat-api.workloft.ai/labs-api/` to Alfred's home IP only. The free public tier we have been talking about for two weeks was, in practice, reachable by exactly one person. It is now actually public.

There is also a debugging lesson worth banking. A previous diagnostic sweep on 20 May looked for explicit Twilio-IP blocks and found none. It did not inspect the catch-all DROP at the tail of DOCKER-USER. Next time a webhook is reaching a provider's edge but never our application, the first place to look is the tail of DOCKER-USER, not the per-IP rules.

## What's still off

Port 80 and 443 are now open from any source. App-level auth and TLS are the only gates. There is no Twilio-CIDR allowlist at L4 and no rate limiting in front of the docker stack. We rely on Traefik and the application to handle abuse. The previous lockdown was overzealous. The new posture sits on the open end.

Before the labs-api free tier sees real public traffic, we will want to put Cloudflare in front of chat-api and tighten the surface again with a per-route policy rather than a global DROP-everything.

And eight days of silently-dropped webhooks meant any call any client could have placed to this number since 14 May went to a dead line. We have notified Twilio support, the ticket is closing, and the line is live from now.
