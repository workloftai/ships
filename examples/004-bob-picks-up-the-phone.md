# Bob Picks Up the Phone

**Date:** 2026-05-21
**Author:** Alfred + Bob
**Category:** agent

After several weeks of back and forth with Twilio support, the Workloft voice line is finally live. Bob, my agent, now answers the phone. You can ring **+44 7380 309850** from any handset, anywhere, and have a real conversation with him in real time. No phone tree. No "press 1 for sales". Just talk.

## What this actually means

Bob has been around for two years as the agent I run my business through over Telegram, my desktop CLI and the Workloft web app. He drafts my outbound posts, triages my inbox, books meetings, remembers what I told him last Tuesday and reminds me about it this Thursday. As of tonight he also has a voice.

The same agent that wrote this article will now pick up if you ring my voice line. You can ask him what Workloft does. You can ask him to take a message. You can ask him to walk you through the labs notes I published last week, or to summarise our pitch, or to find out when I'm next free. He answers in plain English, in real time, in a voice that is closer to a person than a recording.

## Why this matters for the wider market

Voice is where the next leg of practical AI deployment is heading, and the UK business market is wide open for it. Every major lab has shipped a native voice modality inside the last twelve months. Anthropic, OpenAI and Google have all moved voice out of "demo" and into "production". Twilio, Vapi and a small handful of other infrastructure plays are racing to be the substrate. The numbers behind the funding rounds are not subtle.

The shift on the ground is the same shape as the shift from "businesses need a website" twenty years ago to "businesses need a website" being assumed. The next iteration is "businesses need an AI on the phone". The orgs that get there first will catch every after-hours enquiry, every intake call, every appointment that currently falls into a voicemail box no one checks until Monday. The orgs that do not will keep paying a person to answer the same five questions all day. The economics are not balanced.

It is not just about answering. A voice agent that can take a booking, file a ticket, look up an order, send a follow-up email and remember the conversation next time is a different category of front door. It is reachable in the way a chat widget is not. Half the country still rings rather than types when something goes wrong.

## How we got here

The number itself has been provisioned for a week and silent on every test call, which is why a few of you who tried it earlier may have heard a default error message. We filed a P2 ticket with Twilio (#26970247) and spent days swapping diagnostic notes back and forth with their carrier team. Tonight, Jose B on the Twilio side sent the breadcrumb that closed it out, we deployed the fix on our end within five minutes, and the line came up. Real call, real conversation, end to end. Thanks to Jose for the patient diagnostic work.

## What's next

The number is going on every Workloft property over the next few days: the homepage, the pitch deck, every Labs note that argues for putting AI in front of customers. If you want to test it, ring it. Treat it like a normal phone call. Tell Bob who you are and what you want.

The same stack behind it (Twilio voice in, our agent runtime, low-latency speech out) is what we are deploying for clients under the Workloft consulting line. Give your business a voice. We have shown it can be done in a week and a couple of hundred pounds in carrier fees. The blocker is not the technology any more. The blocker is whoever is still answering the same five questions all day.
