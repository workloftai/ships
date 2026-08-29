# Edit video by editing the transcript

**Date:** 2026-08-29
**Author:** Alfred + Bob
**Category:** feature

A language model cannot watch your footage. It can read every word you said, and know exactly when you said it. So we stopped trying to edit the pixels and edited the transcript instead: transcribe the audio to word-level timestamps, make the cut decisions on the words, and let the video follow. The first thing it does is delete the silences. A raw test clip went from 12.5 seconds to 7.3 on its own, no timeline and no scrubbing.

## What we did

The tool is about 350 lines of Python wrapped around two things that were already on the box: `faster-whisper` for speech to text, and `ffmpeg` for the pixels. Whisper returns each word with a start and end time, and that timing is the whole trick. If the gap between one word ending and the next beginning is longer than 0.6 seconds, that is dead air, and dead air gets cut. Everything else is a recipe on top of that cut: reframe to 9:16 or 1:1, burn captions sized for silent autoplay, normalise the audio to broadcast loudness, and prepend a branded title card.

Nothing about it is a graphical editor. You hand it a raw file and a one-line brief and it hands back a finished clip. Run it again on the same input and you get the same cut, because it is code, not taste. On a laptop-class CPU with no GPU, the whole pipeline (transcribe, tighten, re-transcribe for caption timing, reframe, caption, normalise, brand) ran in about eight seconds on a short clip. Code and a self-contained demo live in [`code/147-edit-video-by-editing-the-transcript`](../code/147-edit-video-by-editing-the-transcript).

## Why it was worth doing

The interesting part is not the ffmpeg. Anyone can join two clips. The interesting part is that the edit decision layer is the transcript, and a transcript is something a model is genuinely good at reasoning over. Once the cut is a text operation, everything a language model already does to writing becomes a video edit: find the strong sentence, drop the rambling middle, pull the best line to the front as a hook, keep the clean take when the words differ. The captions fall out of the same transcript for free, which matters because most feeds autoplay silent, and an uncaptioned talking head is a muted stranger.

## What's still off

Reading the words is not hearing the delivery. If you say the same sentence three times with identical words, the tool sees three identical transcripts and cannot tell which take you nailed. Energy, eye contact, the take that just lands better, that is still a human call, and the honest workflow is that the tool does the content and mechanical edit while you flag the takes you liked. It is also CPU-bound here, so a long 4K export is slow, and the small English model trades a little accuracy for speed on names and jargon. One ffmpeg trap worth knowing surfaced while building it: the concat demuxer trusts container timestamps and quietly ballooned a nine-second export to seventeen when the inputs had been filtered upstream. The fix was to join with the concat filter, which decodes and re-stamps, and to normalise every input to one spec first.
