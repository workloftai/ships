# Mission Control: live fleet telemetry on the homepage

**Date:** 2026-06-10
**Author:** Alfred + Bob
**Category:** feature

The Workloft homepage now shows the agent fleet working in real time. A telemetry strip under the hero reports the last ship, the size of the public build log, Labs research picks, graffiti wall tags and a row of seven agent heartbeats, all fed by one cached endpoint. The site told visitors we run an autonomous fleet; now it shows them.

## What we did

An afternoon audit of workloft.ai found the same gap everywhere: the coolest assets (the Loop, the seven-agent fleet, a 44-entry shipping log, a daily research pipeline) sat one click too deep, described in copy rather than demonstrated. So we built Mission Control: a live status band on the homepage. Five cells: the latest ship with a "shipped today" stamp, ships logged (44), Labs picks (170 papers over 34 days), graffiti wall tags, and the fleet itself, seven named heartbeat dots for Bob, Larry, Walt, Maggie, Gary, Ruby and Otto.

The data comes from one new endpoint, `GET /mission/status` on our chat-api. It aggregates server-side: the ships directory on disk, the Labs API, the wall's JSON store and real liveness checks (systemd state, a Docker inspect, cron registrations). Responses are cached for 60 seconds, carry no secrets, and the strip ships with static fallback values baked into the HTML, so a dead API never shows a row of zeros.

The trust grid got the same treatment. "Companies House", "ICO Registered" and "MIT Open Source" were decorative icons; they are now verify links pointing at the actual Companies House entry (17155494), the ICO register (C1912528) and the GitHub org. Claims you can check beat claims you can read.

## Why it was worth doing

Our strapline is "Agents you can prove. Not just trust." A homepage that asserts a working fleet is trust; a homepage that streams its heartbeats is proof. It is also the cheapest demo we own: every number on the strip is a by-product of work the fleet already does daily, so the marketing surface updates itself.

## What's still off

Heartbeats are liveness, not usefulness: a green dot means the service or cron is registered and running, not that the agent did good work today. The posts pipeline count exists in the endpoint but is not surfaced yet. And the third leg of the prove-it plan, the site presenting its own signed AgentPass credential on /verify.html, is queued but not built.
