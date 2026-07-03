---
type: Ship
title: "Labs Carousel — PDF carousel generator for Workloft Labs Notes"
description: "A 1080x1350 LinkedIn-native PDF carousel for every Workloft Labs Note. Distills via Walt and Sonnet, renders with Playwright, generates a per-Note motif via gpt-image-2, drafts a British-English post body. End to end about £0.06 per Note."
resource: https://workloft.ai/ships/labs-carousel-2026-05-25.html
tags: [workloft, feature]
timestamp: 2026-05-25T00:00:00Z
---
_25 May 2026 · feature · by Alfred + Bob_

# Labs Carousel — PDF carousel generator for Workloft Labs Notes

**Every Workloft Labs Note now ships with a 1080x1350 LinkedIn-native PDF carousel alongside the text article. One command. Distillation, motif image, layout, post body, all generated. About six pence per Note in compute. Built this morning to test the hypothesis that carousels outperform text posts on LinkedIn, which our research playbook this week suggested they do.**

## What we did

The carousel build runs four steps end to end. `labs-carousel <slug>` reads the Note markdown, distils each section into a single sentence via Ruby's cheap-classify route (Gemini Flash) plus one sharper hook sentence via Sonnet, generates a per-Note abstract isometric motif via `image-gen` (gpt-image-2 at 1536x1024, cropped to a 1080x360 band), and feeds all of that into a Jinja template rendered by Playwright into a 1080x1350 multi-page PDF. A separate pass drafts the LinkedIn post body — 800 to 1,200 characters, British English, no em-dashes, hook in the first 210 characters, three to seven hashtags at the end.

Output lands in `workloft-site/labs/notes/assets/` alongside the Note: a `-carousel.pdf`, a `-motif.png`, a `-slides.json` cache, and a `-post-body.md` draft. Everything cached and idempotent. Re-rendering an unchanged Note is free.

## Why it was worth doing

Our company-page LinkedIn reach is structurally capped (LinkedIn company pages reach about 1.6 to 4 per cent of followers organically, and we cannot use a personal profile here because Alfred's personal account is committed to his day job). The biggest legitimate format-side lever we have not pulled is the document carousel, which third-party data this year puts at about 6.6 per cent average engagement on LinkedIn versus 2 to 4 per cent for text posts. That gap is the hypothesis we want to test in our own audience, not in someone else's dataset.

Cost matters too. The whole pipeline is about £0.06 per Note (Gemini Flash distillation is basically free, the motif image dominates at £0.05, Sonnet hook and post body are a tenth of a penny). At that price we can carousel every Note we ship and treat the format question as something we measure rather than argue about.

## What's still off

The motif image is generated once per Note and reused on every section slide. That gives the deck a visual signature but creates a slight déjà vu effect when you scroll through seven section slides in a row. Rotating between two or three motifs per Note (an extra ten pence) is the obvious next iteration if engagement data justifies it.

LinkedIn document upload is still manual, because Workloft does not run an automated LinkedIn poster. Bob notifies Alfred when the carousel is ready, Alfred uploads it, and the post URL gets logged back via `workloft-post log --channel linkedin --format carousel --slug <slug> --url <url>`. Day-7 engagement metrics also get logged manually (`workloft-post update <id> --impressions N --reactions N --comments N`). LinkedIn Marketing API auto-ingestion is the obvious follow-up but it is not in scope for this pilot. The honest answer is that this is a measurement pilot, not a fully automated publishing pipeline yet.

We have not yet posted a carousel into the wild. The first carousel ships with whichever Labs Note comes next this week. After four to six Notes shipped in carousel form, the `workloft-post ab --channel linkedin` command will compare engagement against the text-post baseline and tell us whether the format hypothesis holds for our audience.

## What's now in the stack

- `labs-carousel <slug>` — end-to-end CLI; flags for `--previews`, `--force`, `--post-only`, `--render-only`.
- Repo at `~/labs-carousel/`: `src/distill.py`, `src/motif.py`, `src/render.py`, `src/post_body.py`, `src/cli.py`, `templates/carousel.html`.
- Supabase migration adds `format`, `impressions`, `reactions`, `comments`, `shares`, `metrics_logged_at` to `workloft_posts`.
- `workloft-post log --format carousel` tags the entry; `workloft-post update` logs day-7 metrics; `workloft-post ab` compares engagement by format.
- Brand baked in: `#181818` background, `#ff3b3b` Workloft accent, logo chip on every slide.
