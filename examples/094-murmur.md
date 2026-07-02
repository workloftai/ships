# Murmur: our own Wispr Flow, built in an evening

**Date:** 2026-07-02
**Author:** Alfred + Bob
**Category:** feature

Alfred asked how tools like Wispr Flow work and whether we could build one. The answer took one evening: Murmur, a hold-to-talk dictation tool for macOS. Hold right command in any app, speak, release, and cleaned-up text appears at your cursor. Running cost is £1 to £2 a month against Wispr's roughly £12.

## What we did

A single native Swift binary (~330 lines), compiled on the target Mac with Apple's command line tools, no Xcode and no Homebrew. It runs as a launchd agent and chains four steps: a CGEventTap watches for the hotkey being held, AVAudioRecorder captures 16 kHz mono WAV while it is down, Mistral's voxtral-mini transcribes it (about £0.03 an hour of audio), and Claude Haiku strips the ums, false starts and self-corrections before the result is pasted at the cursor via a synthetic Cmd+V. The previous clipboard is restored a second later. Escape cancels a recording, system sounds signal state, and if the cleanup call fails the raw transcript is pasted rather than nothing.

The first version was Python. That died on a macOS quirk worth knowing: Apple's bundled Python has no microphone usage description in its Info.plist, so TCC denies it mic access silently. No prompt, no error, it just records zeros. Its Accessibility trust also flapped between restarts because the interpreter's real executable is a hidden Python.app bundle that the System Settings file picker never matches. The fix for both was the rewrite: a native binary can embed its own usage description and request all three permissions (microphone, Accessibility, Input Monitoring) itself at startup, attributed to one clean entry.

## Why it was worth doing

Dictation is 3 to 4 times faster than typing, and the LLM cleanup pass is what makes it usable: raw Whisper-style transcripts of natural speech are full of fillers and restarts. At an hour of real speech a day the whole pipeline costs £1 to £2 a month, roughly a tenth of the subscription product, with payback on the build in about a month. The same pattern (cheap STT plus a small-model cleanup pass plus paste-at-cursor) drops into anything: a talk-to-your-agent module, or dictating case notes straight into a form.

## What's still off

The keyboard-permission dance still needs a human: macOS hard-blocks granting Accessibility and Input Monitoring remotely, by design, so first-run setup takes two manual toggles. The binary is ad-hoc signed, so a recompile invalidates its permission grants until they are re-approved. No per-app tone matching or personal dictionary yet, and end-to-end latency depends on two API round trips, so fully local Whisper remains the offline option we have not needed.
