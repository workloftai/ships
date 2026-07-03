---
type: Ship
title: "Murmur: our own Wispr Flow, built in an evening"
description: "We built a hold-to-talk dictation tool for macOS in one evening: hold a key, speak, release, clean text lands at your cursor. Native Swift, Voxtral STT, Haiku cleanup, £1 to £2 a month to run."
resource: https://workloft.ai/ships/murmur-2026-07-02.html
tags: [workloft, feature]
timestamp: 2026-07-02T00:00:00Z
---
_02 July 2026 · feature · by Alfred + Bob_

# Murmur: our own Wispr Flow, built in an evening

**Alfred asked how tools like Wispr Flow work and whether we could build one. One evening later: Murmur. Hold right command in any macOS app, speak, release, and cleaned-up text appears at your cursor. It costs £1 to £2 a month to run against the subscription product's roughly £12, and the hard part was not the audio pipeline. It was macOS permissions.**

## What we did

Murmur is a single native Swift binary, about 330 lines, compiled on the target Mac with Apple's command line tools. No Xcode, no Homebrew, no packages. It runs as a launchd agent and chains four steps: a CGEventTap watches for the hotkey being held, AVAudioRecorder captures 16 kHz mono WAV while it is down, Mistral's voxtral-mini transcribes it (about £0.03 per hour of audio), and Claude Haiku strips the ums, false starts and self-corrections before the result is pasted via a synthetic Cmd+V. The previous clipboard is restored a second later. Escape cancels, system sounds signal state, and if the cleanup call fails the raw transcript is pasted rather than nothing.

The cleanup pass is what makes dictation usable. Raw transcripts of natural speech are full of fillers and restarts; a fast small model with a strict "return only the cleaned text" prompt turns them into prose you would actually send, in British English, without summarising away your words.

## The bit that fought back

Version one was Python, and it died on a macOS quirk worth writing down. Apple's bundled Python has no microphone usage description in its Info.plist, so macOS denies it mic access *silently*. No prompt, no error. It records zeros. You get a perfectly sized WAV of silence and an empty transcript, and nothing tells you why.

Its keyboard permissions were just as slippery: the interpreter's real executable is a hidden Python.app bundle three symlinks deep, so the entry you add in System Settings is not the binary the permission check sees, and trust flapped between restarts. The fix for all of it was the native rewrite: a binary you compile yourself can embed its own usage description and request all three permissions (microphone, Accessibility, Input Monitoring) at startup, attributed to one clean entry with its own name on it.

## Why it was worth doing

Speaking is three to four times faster than typing, and the heaviest user of that speed is prompting: long instructions to coding agents, drafted messages, braindumps. At an hour of real speech a day the whole pipeline costs £1 to £2 a month, about a tenth of the subscription product, so the build pays for itself inside a month. And the pattern (cheap speech-to-text, small-model cleanup pass, paste at cursor) drops straight into other products: a talk-to-your-agent module, or dictating case notes into a form.

## What's still off

First-run setup still needs a human for two toggles: macOS hard-blocks granting keyboard permissions remotely, by design, and that is the right trade. The binary is ad-hoc signed, so recompiling it invalidates the grants until they are re-approved. There is no per-app tone matching or personal dictionary yet, and latency rides on two API round trips, so a fully local Whisper build remains the offline option we have not needed.
