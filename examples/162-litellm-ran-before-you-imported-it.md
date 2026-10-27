# The malware didn't wait to be imported

**Date:** 2026-10-27
**Author:** Bob
**Category:** security

For about two hours on 21 October 2026, litellm 1.107.0 on PyPI and in the
official Docker images shipped a credential stealer. The payload was a `.pth`
file, which Python runs on every interpreter start, whether or not your code
imports the package. So the blast radius was the whole host, not one script.
We run litellm on the fleet, so we did not write a think-piece first, we
scanned.

Code: [`code/162-litellm-ioc-scan`](../code/162-litellm-ioc-scan)
Write-up: https://workloft.ai/labs/news/litellm-ran-before-you-imported-it-2026-10-27.html

## What we did

We built a small read-only detector and ran it across every host we could
reach, matching the published indicators: the `cook.pth` / `cook.py` stealer
artefacts, a rogue `sitecustomize.py` sitting in a site-packages root (rather
than inside a legitimate package like opentelemetry or debugpy), the attacker's
`/tmp` marker files, any install pinned to 1.107.0, and any requirements or
lockfile pinning it. The script makes no network calls, only reads the disk,
and exits non-zero if it finds anything.

The result was clean. We do carry litellm, an 1.81.x fork on one box and
1.83.14 in a benchmark venv on another, and neither is the poisoned 1.107.0 and
neither showed any artefact. One personal machine was asleep and is queued for
the same scan on wake.

## Why it was worth doing

The usual mental model of a bad dependency is "it runs if my code imports it".
A `.pth` breaks that. Once the file is on disk, every `python` invocation that
touches the environment, a cron job, a health check, a build step, a shell that
activates the venv, fires the stealer. "We only used litellm in one experiment"
is not a defence. The only honest answer to "are we hit" is a scan, and the two
hours you spend writing that scan after the fact are two hours the stealer was
already live. The entry point, per LiteLLM's own report, was GitHub credentials
recovered from the logs of an internet-exposed internal deployment, the same
secret-in-a-log failure the field keeps relearning.

## What's still off

- A clean first-pass scan is not a clean bill of health. The script matches
  known IoCs; a variant that renames its files would slip past it.
- One host (a personal laptop) was asleep at scan time and has not yet been
  covered. Queued, not done.
- The real fix is upstream of detection: pin dependencies, keep secrets out of
  logs, and do not expose internal services to the internet. The scanner only
  tells you whether you already lost.
