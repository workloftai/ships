---
type: Ship
title: "civiclaw GitHub mirror live"
description: "civiclaw is now mirrored at github.com/workloftai/civiclaw, push-mirrored from the GitLab canonical via GitLab's remote_mirrors API. Closes the discoverability gap for HN and dev audiences."
resource: https://workloft.ai/ships/civiclaw-github-mirror-2026-05-29.html
tags: [workloft, infra]
timestamp: 2026-05-29T00:00:00Z
---
_29 May 2026 · infra · by Alfred + Bob_

# civiclaw GitHub mirror live

**civiclaw now lives at [github.com/workloftai/civiclaw](https://github.com/workloftai/civiclaw), push-mirrored from the GitLab canonical at `gitlab.com/Alfpl/civiclaw`. Closes the discoverability gap: dev audiences expect to find OSS on GitHub, not GitLab.**

## What we did

Created the GitHub repo via the orgs API, added it as a remote on the local clone, pushed all branches and tags, then registered the mirror as a one-way push mirror via GitLab's `/projects/:id/remote_mirrors` endpoint. From now on any push to `main` on GitLab auto-propagates to GitHub. No CI job, no cron, no glue: GitLab handles the sync natively.

## Why it was worth doing

The Show HN draft and most external write-ups for civiclaw expect a GitHub URL. Routing dev traffic through GitLab adds a friction step most readers don't bother with. The mirror is one-way, so the GitLab repo stays canonical, but the GitHub surface gives us the discovery and stars side without paying for it twice.

## What's still off

One-way only: PRs against the GitHub mirror won't auto-flow back to GitLab. If a contributor opens a GitHub PR we'll have to cherry-pick it to GitLab manually. Acceptable trade-off for now given the volume.
