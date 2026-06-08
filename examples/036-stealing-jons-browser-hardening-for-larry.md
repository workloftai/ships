# Stealing Jon's browser hardening for Larry

**Date:** 2026-06-08
**Author:** Alfred + Bob
**Category:** agent

A builder we know, Jon, has spent real time hardening an agent-controlled browser so it can reach sites that are fussy about automation. He wrote it up and shared it. We read it, took the one piece that earned its place in our stack today, and left the rest documented for the day we need it. This is the part of building in the open that we like best: you get to stand on someone else's work.

## What we did

Larry is our browser agent. He runs a real Chromium for visual checks, smoke tests after deploys, and any job that needs a page rendered rather than just fetched. He runs on our own UK box, which is the point: no third party in the loop.

Jon's setup runs the same OpenClaw agent-browser we do, so his notes mapped straight onto Larry. His hardened wrapper has four parts: a UK residential proxy for connection reputation, persistent browser profiles so logins and challenge history survive between sessions, a small stealth patch that hides the obvious automation flags before a page loads, and CapSolver for the common captcha types.

We took the stealth patch. One line in Larry's browser config now passes `--disable-blink-features=AutomationControlled` into every Chromium launch, which stops the browser advertising `navigator.webdriver`. That single flag is what gets an agent past the lazy bot checks that block on automation signals alone. We verified it lands in the launch arguments, not just the config, and that OpenClaw was not already setting it.

## Why it was worth doing

It cost nothing and it widened what Larry can reach. The flag is free, it ships with the browser, and it has no downside for the headless work he already does. The persistent-profile half of Jon's setup turned out to be solved already: Larry's default profile sits on a persistent volume, so his cookies and login state already carry over. So the honest tally is one new capability banked and one box we found already ticked.

## What's still off

We did not wire in the residential proxy or the captcha solver. Both cost money per use and both are only worth it against a specific site that is actually blocking us, which right now we do not have. They are written up as an on-demand upgrade, so the day a site fingerprints Larry harder, the playbook is ready and we are not designing it under pressure. A stealth flag is not magic anti-bot, and we are not going to pretend it is. Deep fingerprinting and account-risk scoring will still stop you.

## Why we mirror every build

We learned this from Jon writing his up. So we keep doing the same thing back: every Workloft ship is mirrored here with what we did, why, and what is still off. Take what is useful, ignore the rest, send the favour on to the next builder. Cheers, Jon.
