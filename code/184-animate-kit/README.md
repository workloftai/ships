# animate-kit

Agent-driven 3D explainer animations: Claude writes a Blender scene in Python, a headless Blender on an Apple-silicon Mac renders it, ffmpeg encodes it, and an independent reviewer gates it before a human sees it.

## Files
- `make_tex.py`: PIL textures (labels, badges) in the brand font. Writes `tex/`.
- `scene.py`: the whole scene as code. Helpers: `mat`, `cyl`, `box`, `plane`, `img_mat`, `swap_mat` (label cross-fade), `curved_label`, `pop`/`unpop`, `keyv` (animate node sockets), Bezier "reach" curves with a packet on a Follow Path, area lights, a cyclorama, a Track To camera with depth of field. Modes: `still <pct> <frame>`, `anim <pct> [start end]`, `inspect`. The example scene is a "chef reads the label" MCP explainer: replace the scene, keep the helpers.
- `push_render.sh`: ships `scene.py` + `tex/` to the Mac mini and renders with EEVEE (`still`, `anim`, `inspect`).
- `finish.sh`: pulls frames back, encodes MP4 (x264 crf 17), GIF (Bayer dither, 160 colours) and a 1fps contact sheet.
- `composite.py`: optional 2D overlay (titles, chips, captions) over the frames.

## Loop
1. `cp -r ~/animate-kit <project>` and `cd` into it. `python3 make_tex.py`.
2. Beat plan first (5-7 beats with times).
3. Stills at 50% until the key frames are right: `./push_render.sh still 50 60 180 300`.
4. One full render: `./push_render.sh anim 80` (about 4 s per 1280x760 frame on an M2).
5. `NAME=my-explainer ./finish.sh`, look at `contact.png`, then the independent review.

See `~/.claude/skills/animate/SKILL.md` for the quality bar and the gotchas.
