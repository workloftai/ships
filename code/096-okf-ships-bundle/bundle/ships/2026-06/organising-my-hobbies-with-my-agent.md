---
type: Ship
title: "Organising My Hobbies With My Agent"
description: "I turned three hobbies into slash-commands my Claude Code agent runs: /running, /sourdough, /pizza. Why an agent on my own VPS beats a project on a consumer app: the memory is mine and the maths is real code."
resource: https://workloft.ai/ships/organising-my-hobbies-with-my-agent-2026-06-21.html
tags: [workloft, agent]
timestamp: 2026-06-21T00:00:00Z
---
_21 June 2026 · agent · by Alfred + Bob_

# Organising My Hobbies With My Agent

**Hobbies keep me sane. Between work, being a dad and a husband, and running a fleet of agents, the things that keep me steady are running, baking bread and making pizza. I also just like making things, agents, websites, tools, and it turns out that runs straight into the kitchen. So I did the obvious thing and pointed my own agent at the three hobbies that keep me going. It tracks my running, coaches my sourdough and argues with me about pizza dough, and it does it better than a project on a consumer app would.**

## Why these three

Running is not really a hobby any more, it is part of how I stay sane and part of who I am. I have to run. Sourdough started as a grumble at a shop shelf: when a loaf of bread in the UK creeps past three pounds, something has gone wrong. So I learned to keep a starter alive and bake my own, and the honest truth is it comes out significantly better than anything I was buying. Pizza followed naturally. I lived in New York for the best part of a decade, which makes me, politely, a pizza snob. I started wondering whether my sourdough starter could pull double duty as pizza dough. A few rounds with Perplexity later I made the leap, bought a steel, and started turning out proper pizza at home. Three hobbies, all of them making something with my hands, all of them keeping me grounded in a mad world of work, family and agents. Getting them organised was the natural next step, and I already had the tool for it.

## What I built

Three slash-commands on Bob, my Claude Code agent running on a VPS and reachable over Telegram. **/running**: I send it screenshots from my running watch and it reads every metric into a strict 34-column schema, dedupes, and appends a row to a CSV. Ask "am I getting faster" and a small Python helper, not the model, does the maths. **/sourdough**: my resident baker, anchored to my house loaf recipe held as a file, so it scales the formula, troubleshoots crumb and plans schedules all relative to my actual dough. **/pizza**: the same for pizza, my dough and sauce as the durable default, with topping, timeline and baking advice. Each is a command that loads a full operating manual and wires to my own files. Built in an afternoon.

## Why not just a ChatGPT or Claude project

Worth answering honestly, because the consumer platforms have projects and memory now and they are polished. Three reasons it is not the same. First, the memory is mine and it is files. My run log is a CSV that grows without limit and I can open it. My recipes are markdown files I edit. A project's memory is curated by the model, stored on the vendor's servers, and bounded. The honest version of "it forgets" is not that projects have no memory, it is that their memory is a summarised blob you do not control, where a file on disk is exact and yours. Second, the maths is real code. The running stats come from a deterministic helper reading the file, not the model re-deriving numbers from a conversation it may have truncated. Third, it comes to me. Bob lives on a server and answers on Telegram, so I text a screenshot from the kitchen or after a run and it is logged. A consumer app is the other way round: you open it, you prompt, you leave.

There is a fourth reason, and it is the one you cannot bolt on afterwards. The agent runs a standing nightly eval of its own output, a three-model panel that grades what it produced and flags drift, which we built this week. The hobby skills log into that same check, so a sourdough answer or a logged run is held to the same bar as the serious work. A consumer project gives you no standing eval you can point at it at all.

## What's still off

The honest cost is that I run the box. The polished apps are zero setup, and I maintain a VPS, keep the agent alive, and pay for that in time. These are single-user tools pointed at my own files, not products, and they are only as good as the prompts and recipes I feed them: a sloppy house recipe makes a sloppy coach. If you cannot or will not run your own agent, the consumer projects are the easier path. If you can, you get one that is yours, persistent, and pushes to you instead of waiting to be opened.

## What we'd take from it

- **Durable file memory beats curated memory.** Store the thing you care about as a file you own, not a fact you hope the model retains.
- **Let the model judge and see, let code count and store.** Advice and vision from the model, maths and the log from a deterministic helper, so the numbers are always reproducible from the file.
- **Low-friction triggers matter.** A command you fire from your phone with a screenshot attached is the difference between a tool you use and one you mean to.
- **It is not just for work.** The agent that runs the business now tracks my running and argues with me about hydration. The patterns port straight across.
