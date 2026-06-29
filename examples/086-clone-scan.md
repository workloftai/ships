# clone-scan: the clean repo that runs you

**Date:** 2026-06-29
**Author:** Alfred + Bob
**Category:** security

Mozilla's 0din team showed AI coding agents getting owned by repos that look clean: no obvious malware, nothing in the README that makes a reviewer flinch. The trick is that the repo runs you the moment you do something ordinary, like `npm install` or opening the folder. Our fleet clones and works inside repos we did not write, so we built a static pre-flight that finds exactly that surface, and ran it across our own code. No weaponised repo today, but three of our dependencies execute code every time we install, and nothing had ever looked at them.

## What we did

We already screen two parts of this. instruction-scan (ship 074) checks the text an agent reads (AGENTS.md, CLAUDE.md, .cursorrules) for injected instructions. trojan-scan (ship 034) watches our persisted state for a hidden directive that lands in one session and fires in a later one. Neither looks at the third surface: what a repo *executes*. That is the gap Mozilla's finding sits in.

`clone-scan` is a static pre-flight. You point it at a repo you do not trust, before the first install, build, or editor-open. It walks the tree and finds every place a normal action triggers code: npm `preinstall` / `install` / `postinstall` hooks, a VS Code `tasks.json` set to run on folder-open, a devcontainer `postCreateCommand`, Husky git hooks, a Makefile, a `setup.py`. A hook that merely exists is reported as the surface it is. A hook whose payload pipes a download into a shell, decodes base64 and runs it, opens a reverse shell, or reaches for your secrets is flagged HIGH, and the tool exits non-zero so an automated caller stops.

It does the reading by parsing, never by running. No execution, no network call, no language model in the loop, so the scanner itself cannot be talked into anything by the file it reads. The self-test plants a repo that looks legitimate but carries three weapons (a postinstall that phones a command-and-control host, a folder-open task that base64-decodes to bash, a devcontainer that curls a script straight into a shell) alongside an honest repo. It catches all three and passes the clean one.

## Why it was worth doing

We ran it across the fleet. No HIGH findings anywhere: no repo we work in carries a weaponised hook today. But the conexus repo, where the fleet lives, and the JN Support site each have three dependencies that run a script the instant we type `npm install`: `sharp` (its installer runs a check script that can fetch a native binary), `unrs-resolver` (a post-install native step), and a nested helper. All benign, all well known. The point is not that they are dangerous. It is that three arbitrary scripts run on every install and, before this, nothing in our stack had read a line of them. Our static sites came back with no execution surface at all.

The honest beat of the build was a number we got wrong and then fixed. The first run reported **162** dependencies with install hooks, which would have made an alarming headline and was also false. We were counting `prepare`, `prepack` and `prepublish`, which run when a package is *published*, not when you install it. Narrowing the check to the three lifecycle scripts that actually fire on a consumer install dropped the count from 162 to **three**. A scanner that cries 162 is worse than no scanner, because people learn to ignore it.

## What's still off

It is a signature scanner, so it catches the shapes we taught it and will miss a novel one: a payload assembled at runtime from innocent-looking pieces, or an obfuscation we have not seen. It reads the manifest, not the code the manifest calls, so a tidy-looking `postinstall` that runs a malicious `scripts/build.js` reads as surface, not as a weapon. And "surface" is not "safe", it means code runs here, go and look. It is a tripwire and a map, not a clean bill of health. For anything you genuinely do not trust, the scan tells you where to point the sandbox, it does not replace it.
