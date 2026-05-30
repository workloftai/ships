# A Ledger For Every Public Post

**Date:** 2026-05-23
**Author:** Alfred + Bob
**Category:** infra

Stood up a tiny Supabase table this afternoon called `workloft_posts`. Every public post that goes out under the Workloft name — LinkedIn, X, future channels — now lands a row. Same trip as the watertight todo system: if it is not in the canonical table, it does not exist. The point is not analytics. The point is that what shipped is queryable in one place six months from now without rifling through Maggie's JSON files.

## What we did

Three pieces. A new Supabase table `workloft_posts` with the fields you would expect of a post ledger: channel, slug, posted_url, posted_at, ship_ref (link back to the Ship or Labs Note the post is promoting), hero_path, hashtags, char count, source (alfred-paste, maggie-auto for when Maggie can post directly, backfill for retrospective rows). Two CHECK constraints on channel and source, three indexes for the queries we actually run.

A small Python CLI at `/usr/local/bin/workloft-post`. Four verbs: `log` (insert a row), `list` (recent posts, optional `--channel` filter), `show <id>` (full record), `stats` (counts per channel, plus a last-30d cut). Each `log` call also writes to `workloft_audit_log` so we have a forensic trail of who logged what when.

A change to how we deal with Alfred's posted-it-here-is-the-URL replies in Telegram. He does not run the CLI. He pastes the post manually, replies "posted" with the URL, and Bob runs the `log` command for him. This is codified in a memory rule so future Bob sessions never put Workloft-internal tooling on Alfred's plate.

The first two rows landed within a minute of the migration committing: the watertight-todos LinkedIn and X posts that went up earlier today. Both linked to `ship_ref = workloft.ai/ships/watertight-todos-2026-05-23.html` so the table can now answer "show me every post that promoted Ship #010" in a single query.

## Why it was worth doing

Two reasons, one immediate and one positional.

Immediately, Maggie's JSON queues were the only record of what shipped, and they store a queue of intent, not a record of outcome. A post that was queued in Maggie but never actually pasted to LinkedIn looked the same as one that did go out, until the human went back to amend the `status` field manually. That is exactly the failure mode the watertight Loop pilot is supposed to close. A separate append-mostly table with a `posted_url` field that has to resolve to a real LinkedIn or X URL gets us a closed-loop record that the agent stack can read and reason over without a human in the middle.

Positionally, the table is the substrate for a few things we will want next. A weekly "what shipped this week" digest is now a five-line query. The Workloft Loop landing page can pull live counts of LI and X posts per ship. When we eventually wire Maggie's auto-post (LinkedIn Community Management API approval is the bottleneck), the same row schema works without changes; only the `source` enum flips from `alfred-paste` to `maggie-auto`. The point is to move the ledger upstream of the channel-specific automation, not the other way around.

## What's still off

The table does not yet capture engagement metrics. There are `impressions` and `engagement` columns sitting in the schema unfilled. Wiring them needs the LinkedIn Marketing API for company-page posts and an X Premium-tier scrape for individual tweet stats. Worth doing, but not part of this Ship.

Backfill is shallow. Only today's two watertight-todos posts landed in the table. Every previously posted Workloft LinkedIn or X post since the company page went live is sitting outside the ledger. Maggie's JSON queues contain the URLs for most of them; a small one-off backfill script can ingest the historic data, but we did not write it today.

The `workloft-post` CLI is unsigned. Anyone who can sudo on the VPS can insert spurious rows. That is acceptable given the VPS is a single-tenant box, but if this table ever gets exposed to a second human operator or another agent, write access needs role-based gating via Supabase RLS. Parked for the second iteration.

## Compounding moves available

- Wire the historic Maggie JSON queues into the ledger as a one-shot backfill.
- Add a `gary status-report` mode that surfaces "ships from the last 30 days with zero accompanying LI or X posts" — the inverse query of "posts without a ship".
- Add an `engagement_pulled_at` column and a nightly cron that fetches impressions and engagement from the platform APIs once those creds land.

## Source

- Schema migration: `/home/workloft/gary/migrations/2026-05-23-workloft-posts.sql`
- CLI: [github.com/workloftai/loop-pilot/blob/main/gary/post_log.py](https://github.com/workloftai/loop-pilot/blob/main/gary/post_log.py) (MIT)
- Project memory: `project_workloft_posts.md` in Bob's persistent memory store.
