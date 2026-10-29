# We gave Claude a Blender and a strict reviewer

**Date:** 2026-10-29
**Author:** Alfred + Bob
**Category:** feature

Claude can build polished 3D explainer animations in a headless Blender, but the first cut is never the one to ship: an independent reviewer model sent both of our first two animations back before a human saw them. We turned that into a routine called `/animate`: a fresh agent writes the scene as Python, a Mac mini renders it, and a second model plays strict creative director.

Code: [`code/184-animate-kit`](../code/184-animate-kit) (scene, textures, render and encode scripts, and the skill file).

## What we did

We make short looping explainer animations to sit beside a presenter in video. They used to be flat SVG drawn frame by frame in a headless browser. We installed Blender 5.2 on an M2 Mac mini (8GB) and let Claude drive it with no window open: the whole scene, lights, camera moves and timeline are a Python script, rendered over SSH with EEVEE at about 4 to 6 seconds a frame at 1280x760. Frames come back, ffmpeg encodes an MP4 and a GIF, and a one-frame-per-second contact sheet goes to review.

The `/animate` skill fixes the order: beat plan first, 50% stills only until the key frames are right, then exactly one full render, then the review. The build always runs in a fresh agent, because most of the cost of a long session is re-reading its own history.

## Why it was worth doing

A separate, cheaper model gets the contact sheet, four full frames and the original, and must answer SHIP, FIX-FIRST or BELOW-PAR. It said FIX-FIRST to both of our first two animations, and it was right: a scanning beam that read as a render seam, a finale with no visible payoff, connection lines that piled into spaghetti, the "problem" colour used in the happy ending, and fixed items that kept a grey X. None of these are bugs a test finds. They are what a viewer notices in two seconds and a builder stops seeing after twenty minutes.

One real bug: Blender's `transform_apply` applies location as well as scale by default, so pop-in badges flew in from the middle of the world for a few frames. One flag (`location=False`) fixed it, after a wasted 30-minute render.

Cost: the first piece, built inside a long working session, used about 4% of a normal week's Claude usage on our box and 2.5 full renders. The second, built by a fresh agent from the kit, took one full render plus one fix render and noticeably less usage. Our target is 1 to 2% of a week per animation, an estimate until we have run a few.

## What's still off

The Mac mini sleeps and has 8GB of memory, so this suits clean explainer scenes, not cinema. GIFs with a moving camera land around 20MB, so the MP4 is the real deliverable. And the reviewer is a model too: it once mistook a landing frame for a missing animation, so we still check its claims against the frames.

## How to use the kit

Set `RENDER_HOST` to the SSH target of a Mac with Blender 5.x at `/Applications/Blender.app`, and `ANIMATE_FONT` to a TTF. Then `cp -r 184-animate-kit my-job && cd my-job && python3 make_tex.py`, iterate with `./push_render.sh still 50 60 180 300`, render once with `./push_render.sh anim 80`, and encode with `NAME=my-job ./finish.sh`. The example scene is a "chef reads the label" MCP explainer: replace the scene, keep the helpers. `SKILL.md` holds the quality bar and the gotchas.
