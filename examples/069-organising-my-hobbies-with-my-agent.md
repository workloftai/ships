# Organising My Hobbies With My Agent

**Date:** 2026-06-21
**Author:** Alfred + Bob
**Category:** agent

I spent an afternoon turning three of my hobbies into commands my agent runs. /running logs my runs, /sourdough coaches my bread, /pizza coaches my dough. The hobbies are not the point. The point is that a Claude Code agent on my own server does this better than a project on a consumer app, because the memory is mine to read and the maths is real code, not a model's recollection of a chat.

## What we did

Three slash-commands on Bob, my Claude Code agent running on a VPS and reachable over Telegram. **/running**: I send it screenshots from my running watch and it reads every metric into a strict 34-column schema, dedupes, and appends a row to a CSV. Ask "am I getting faster" and a small Python helper, not the model, does the maths. **/sourdough**: my resident baker, anchored to my house loaf recipe held as a file, so it scales the formula, troubleshoots crumb and plans schedules all relative to my actual dough. **/pizza**: the same for pizza, my dough and sauce as the durable default, with topping, timeline and baking advice. Each is a command that loads a full operating manual and wires to my own files. Built in an afternoon.

## Why not just a ChatGPT or Claude project

Worth answering honestly, because the consumer platforms have projects and memory now and they are polished. Three reasons it is not the same. First, the memory is mine and it is files. My run log is a CSV that grows without limit and I can open it. My recipes are markdown files I edit. A project's memory is curated by the model, stored on the vendor's servers, and bounded. The honest version of "it forgets" is not that projects have no memory, it is that their memory is a summarised blob you do not control, where a file on disk is exact and yours. Second, the maths is real code. The running stats come from a deterministic helper reading the file, not the model re-deriving numbers from a conversation it may have truncated. Third, it comes to me. Bob lives on a server and answers on Telegram, so I text a screenshot from the kitchen or after a run and it is logged. A consumer app is the other way round: you open it, you prompt, you leave.

## What's still off

The honest cost is that I run the box. The polished apps are zero setup, and I maintain a VPS, keep the agent alive, and pay for that in time. These are single-user tools pointed at my own files, not products, and they are only as good as the prompts and recipes I feed them: a sloppy house recipe makes a sloppy coach. If you cannot or will not run your own agent, the consumer projects are the easier path. If you can, you get one that is yours, persistent, and pushes to you instead of waiting to be opened.
