# vidkit — edit talking-head video by editing its transcript

You do not need to *watch* footage to cut it well. Transcribe the audio to
word-level timestamps, make the edit decisions on the words, then let the video
follow. `ffmpeg` does the pixels; the transcript is the brain.

The first thing it does is delete the silences: any gap longer than
`--max-silence` (default 0.6s) between one word ending and the next beginning is
dead air, and gets cut. On top of that cut it reframes for vertical/square feeds,
burns captions sized for silent autoplay, normalises loudness, and can prepend a
branded title card. Same input, same output, every time, because it is a recipe
not a timeline.

## Requirements

- `ffmpeg` and `ffprobe` on PATH (a normal build; needs `libass` for captions
  and `libfreetype` for the title card, both standard).
- `pip install faster-whisper` (CPU int8 by default, no GPU required).

## Try it with no footage of your own

```bash
pip install faster-whisper
bash demo.sh
```

`demo.sh` synthesises a short talking-head clip with real speech and deliberate
silences (via ffmpeg's built-in flite TTS), then runs the full pipeline. On a
laptop CPU the whole thing finishes in a few seconds, and the ~12.5s raw clip
comes out around 7.3s once the dead air is cut.

## On your own clip

```bash
# raw -> platform-ready in one pass
python3 vidkit.py pipeline raw.mp4 -o out.mp4 --aspect 9:16 --title "Workloft"

# or run any stage on its own
python3 vidkit.py transcribe raw.mp4 --srt        # words + .srt
python3 vidkit.py tighten    raw.mp4 -o tight.mp4  # cut the silences
python3 vidkit.py captions   raw.mp4 -o cap.mp4    # burn silent-autoplay captions
python3 vidkit.py reframe    raw.mp4 -o vert.mp4 --aspect 9:16
```

Flags worth knowing: `--max-silence` (how long a pause must be before it is cut),
`--aspect` (`9:16`, `1:1`, `16:9`, `4:5`), `--model` (any faster-whisper size;
`base.en` is the quick default, `small.en` is more accurate on names and jargon),
`--title` (title-card text, omit for none).

## What it does not do

Reading the words is not hearing the delivery. If you record the same line three
times with identical words, it sees three identical transcripts and cannot tell
which take you nailed. Energy, eye contact, the take that just lands better, that
is a human call. The honest split is: this does the content and mechanical edit,
you flag the good takes. It is CPU-bound, so long 4K exports are slow.

## One ffmpeg gotcha it already handles

The concat *demuxer* trusts container timestamps and will balloon a duration
when its inputs have been filtered/re-encoded upstream (a 9s export became 17s in
testing). `vidkit` joins with the concat *filter* instead, which decodes and
re-stamps, and normalises every input to one spec (size, square pixels, 30 fps,
48 kHz stereo) before joining. If you write your own ffmpeg glue, borrow that.

MIT, part of [Workloft Ships](https://workloft.ai/ships/). Steal what you like.
