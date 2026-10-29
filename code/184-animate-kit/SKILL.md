---
name: animate
description: Build a polished 3D explainer animation (MP4 + GIF) with headless Blender on the Mac mini, from a story or an existing flat animation, quality-gated by an independent reviewer before Alfred sees it. Use on /animate, or when Alfred asks to "elevate", "do in 3D" or "animate" a story. Lean by design: fresh agent, stills first, ONE full render.
---

# /animate — 3D explainer animations, one command

The goal: roughly one animation a week on a usage budget you can see. This is the routine that delivered our first two pieces (29 Oct 2026). Follow it in order.

## 0. Inputs (ask only if genuinely missing)
- The story: a talk track, a flat GIF/MP4 to elevate, or a one-paragraph brief.
- Where it plays: default = a landscape window beside a presenter (1280x760). Pure animation, **no text overlays** unless he asks (in-world 3D labels/badges are fine).
- Brand: pick one accent for "problem / agent call" and one for "resolved", and never swap them.

## 1. Delegate the build to a FRESH agent (this is the usage saving)
Do not build in a long main session. Spawn one `general-purpose` agent with a self-contained brief:
- Copy the kit: `cp -r animate-kit <job>/`. Never edit `~/animate-kit` itself.
- Read `~/animate-kit/README.md` and `scene.py` fully first; adapt the scene, keep the helpers.
- Write a 5-7 beat plan with times before modelling anything.
- Stills only at 50% (`./push_render.sh still 50 <frames...>`), contact-sheeted with PIL; max ~4 rounds.
- Check pops mid-scale (`./push_render.sh inspect`) so nothing animates from a wrong origin.
- ONE full render at 80% (`./push_render.sh anim 80`, ~4s/frame, ~14 min for 12s), then `NAME=<name> ./finish.sh`.
- Re-render only affected frame ranges if a glitch appears.
- Report: paths, beat plan, known weak spots, number of full renders. No messaging the human.
Paste the quality bar (section 3) and gotchas (section 4) into the brief.

## 2. Gate it yourself, then independently
1. Read `contact.png` and 2-4 full-res frames yourself. Glitches = send back.
2. Spawn a `general-purpose` agent with `model: sonnet` as a strict creative director: give it the contact sheet, 4 keyframes, the original (if elevating) and the story; ask for VERDICT SHIP / FIX-FIRST / BELOW-PAR, readability per beat without captions, top 3 defects with times, better-than-original yes/no. Under 180 words.
3. FIX-FIRST → SendMessage the build agent with the exact fixes, one more full render, re-gate. Max two gate rounds.
4. Only SHIP reaches the human. "If the asset is below par, don't surface it."

## 3. Quality bar (from the reviewer's verdicts on the first two)
- Every beat reads WITHOUT captions: each state change has a visible change (colour, motion, badge, object), not a thin line.
- The finale has visible contrast vs the start (lights up, glows, tidies). Payoff, not a static hold.
- No clutter: retract or fade old connection lines before new ones start; lines reach only their own target.
- Colour semantics stay consistent (orange = problem/agent call, teal = resolved). Don't use the problem colour in the happy ending.
- "Resolved" must look resolved (tick or neutral dash, never a grey X).
- The agent character acts (lean, nod, shake, recoil, hop) and its shape is instantly recognisable.
- End on a calm living hold (subtle motion) so it can sit behind a speaker.

## 4. Gotchas (do not relearn)
- `transform_apply` defaults `location=True`: origins jump to (0,0,0) and pops fly in. Always `location=False, rotation=False, scale=True`.
- `obj.parent = p` sets no inverse: child location becomes local to the parent.
- Blender 5.2: no `Action.fcurves`; animate node sockets with `keyframe_insert("default_value")` (see `keyv`). Engine id `BLENDER_EEVEE`.
- Use Standard view transform (AgX washes out brand colours) and stylised alpha glass (BLENDED, alpha ~0.16) over true transmission.
- Mac mini is zsh: unmatched globs error; use `find ... -delete`. It sleeps: if ssh times out, it needs waking. 8GB RAM: keep scenes light. Don't render on a GPU-less server.
- GIFs over 10MB fail Telegram's sendPhoto: send the MP4 and a zipped GIF.

## 5. Deliver
The MP4 + zipped GIF, a 4-5 line beat summary, what the gate caught and fixed, renders used.
