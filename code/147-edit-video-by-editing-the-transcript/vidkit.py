#!/usr/bin/env python3
"""
vidkit — edit talking-head video by editing its transcript.

The idea: you don't need to *watch* footage to cut it well. Transcribe the
audio to word-level timestamps, make the edit decisions on the words (drop the
silence, drop the filler, keep the good line), then let the video follow the
words. ffmpeg does the pixels; the transcript is the brain.

Dependencies: ffmpeg/ffprobe on PATH, and faster-whisper in this venv.
No GPU required (CPU int8). No cloud calls.

Subcommands:
  transcribe   audio -> word-level JSON + .srt
  tighten      auto-cut long silences/gaps using the transcript
  captions     burn silent-autoplay captions (from transcript or an .srt)
  reframe      crop to 9:16 / 1:1 / 16:9, centre-safe
  brand        prepend a title card and normalise audio
  pipeline     raw -> platform-ready in one pass (default preset: li)

Everything is a repeatable recipe. Run it again, get the same cut.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

# --- small shell helpers -----------------------------------------------------

def run(cmd, **kw):
    """Run a command, raising with the stderr tail if it fails."""
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        tail = "\n".join((p.stderr or "").strip().splitlines()[-8:])
        raise RuntimeError(f"command failed: {' '.join(cmd[:3])}...\n{tail}")
    return p


def probe_duration(path):
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path])
    return float(p.stdout.strip())


def probe_dims(path):
    p = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", path])
    w, h = p.stdout.strip().split("x")
    return int(w), int(h)


# --- transcription -----------------------------------------------------------

def transcribe_words(path, model_size="base.en"):
    """Return a flat list of {word, start, end} from the audio."""
    from faster_whisper import WhisperModel  # imported lazily; heavy
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(path, word_timestamps=True, vad_filter=True)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
    return words


def _fmt_ts(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def words_to_srt(words, max_chars=42, max_gap=0.8):
    """Group words into short caption cues (silent-autoplay friendly)."""
    cues, cur, start = [], [], None
    for w in words:
        if start is None:
            start = w["start"]
        prospective = " ".join([x["word"] for x in cur] + [w["word"]])
        gap = w["start"] - cur[-1]["end"] if cur else 0
        if cur and (len(prospective) > max_chars or gap > max_gap):
            cues.append((start, cur[-1]["end"], " ".join(x["word"] for x in cur)))
            cur, start = [], w["start"]
        cur.append(w)
    if cur:
        cues.append((start, cur[-1]["end"], " ".join(x["word"] for x in cur)))
    out = []
    for i, (a, b, text) in enumerate(cues, 1):
        out.append(f"{i}\n{_fmt_ts(a)} --> {_fmt_ts(b)}\n{text}\n")
    return "\n".join(out)


# --- transcript-as-edit-brain: silence tightening ----------------------------

def keep_segments(words, duration, max_silence=0.6, pad=0.15):
    """
    From word timestamps, compute the spans of video worth keeping: the talking,
    plus a little padding, with any gap longer than max_silence collapsed.
    Returns a list of (start, end) to KEEP, in order.
    """
    if not words:
        return [(0.0, duration)]
    spans = []
    seg_start = max(0.0, words[0]["start"] - pad)
    prev_end = words[0]["end"]
    for w in words[1:]:
        gap = w["start"] - prev_end
        if gap > max_silence:
            # close the current keep-span (pad the tail), open a new one
            spans.append((seg_start, min(duration, prev_end + pad)))
            seg_start = max(0.0, w["start"] - pad)
        prev_end = w["end"]
    spans.append((seg_start, min(duration, prev_end + pad)))
    # merge any spans that now touch/overlap after padding
    merged = [spans[0]]
    for a, b in spans[1:]:
        if a <= merged[-1][1] + 0.02:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def cut_to_segments(inp, spans, out):
    """Concatenate the kept spans into one file, re-encoding for clean joins."""
    if len(spans) == 1 and spans[0][0] < 0.05:
        # nothing to cut
        run(["ffmpeg", "-y", "-i", inp, "-c", "copy", out])
        return
    parts = []
    for a, b in spans:
        parts.append(f"between(t,{a:.3f},{b:.3f})")
    select = "+".join(parts)
    vf = f"select='{select}',setpts=N/FRAME_RATE/TB"
    af = f"aselect='{select}',asetpts=N/SR/TB"
    run(["ffmpeg", "-y", "-i", inp, "-vf", vf, "-af", af,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "160k", out])


# --- captions ----------------------------------------------------------------

# Silent-autoplay caption style: bold, high-contrast, bottom third.
CAPTION_STYLE = (
    "FontName=DejaVu Sans,Fontsize=15,Bold=1,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,"
    "Alignment=2,MarginV=48"
)


def burn_captions(inp, srt_path, out, style=CAPTION_STYLE):
    esc = srt_path.replace("'", r"\'")
    run(["ffmpeg", "-y", "-i", inp,
         "-vf", f"subtitles='{esc}':force_style='{style}'",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "copy", out])


# --- reframe -----------------------------------------------------------------

ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080),
           "4:5": (1080, 1350)}


def reframe(inp, out, aspect="9:16"):
    tw, th = ASPECTS[aspect]
    # scale to cover, centre-crop to the target box, force square pixels
    # (crop rounding can otherwise leave a non-1:1 SAR that breaks later joins)
    vf = (f"scale={tw}:{th}:force_original_aspect_ratio=increase,"
          f"crop={tw}:{th},setsar=1")
    run(["ffmpeg", "-y", "-i", inp, "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "copy", out])


# --- brand + audio -----------------------------------------------------------

def make_title_card(text, dims, seconds, out):
    w, h = dims
    safe = text.replace(":", r"\:").replace("'", r"’")
    vf = (f"drawtext=text='{safe}':fontcolor=white:fontsize={int(h/14)}:"
          f"x=(w-text_w)/2:y=(h-text_h)/2:font=DejaVu Sans")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"color=c=0x0a0a0a:s={w}x{h}:d={seconds}",
         "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
         "-vf", vf, "-t", str(seconds),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p", out])


def normalise_audio(inp, out):
    run(["ffmpeg", "-y", "-i", inp, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", out])


def concat_reencode(clips, out, dims):
    """
    Join clips via the concat *filter* (not the demuxer). The demuxer trusts
    container timestamps and balloons the duration when inputs have been
    filtered/re-encoded upstream; the filter decodes and re-stamps. We also
    normalise every input to one canonical spec (target size, square pixels,
    30 fps, 48 kHz stereo) inside the graph, so mismatched sample rates or SAR
    from earlier stages can't reinitialise-error the filter.
    """
    w, h = dims
    inputs = []
    for c in clips:
        inputs += ["-i", c]
    pre, cat = [], ""
    for i in range(len(clips)):
        pre.append(f"[{i}:v]scale={w}:{h},setsar=1,fps=30[v{i}]")
        pre.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
        cat += f"[v{i}][a{i}]"
    fc = ";".join(pre) + f";{cat}concat=n={len(clips)}:v=1:a=1[v][a]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", fc,
         "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p", out])


# --- pipeline ----------------------------------------------------------------

def pipeline(inp, out, aspect="9:16", title=None, model_size="base.en",
             max_silence=0.6, tmp=None):
    tmp = tmp or tempfile.mkdtemp(prefix="vidkit_")
    log = lambda m: print(f"[vidkit] {m}", file=sys.stderr)

    log("transcribing (word timestamps)...")
    words = transcribe_words(inp, model_size)
    log(f"  {len(words)} words")

    dur = probe_duration(inp)
    spans = keep_segments(words, dur, max_silence=max_silence)
    kept = sum(b - a for a, b in spans)
    log(f"tighten: {dur:.1f}s -> {kept:.1f}s ({len(spans)} spans kept)")
    tightened = os.path.join(tmp, "tight.mp4")
    cut_to_segments(inp, spans, tightened)

    # re-transcribe the tightened cut so caption timings line up
    log("re-transcribing tightened cut for caption timing...")
    words2 = transcribe_words(tightened, model_size)
    srt = os.path.join(tmp, "cap.srt")
    with open(srt, "w") as f:
        f.write(words_to_srt(words2))

    log(f"reframe -> {aspect}")
    framed = os.path.join(tmp, "framed.mp4")
    reframe(tightened, framed, aspect)

    log("burning captions...")
    capped = os.path.join(tmp, "capped.mp4")
    burn_captions(framed, srt, capped)

    log("normalising audio (-16 LUFS)...")
    normed = os.path.join(tmp, "normed.mp4")
    normalise_audio(capped, normed)

    body = normed
    if title:
        log(f"title card: {title!r}")
        dims = ASPECTS[aspect]
        card = os.path.join(tmp, "card.mp4")
        make_title_card(title, dims, 1.6, card)
        concat_reencode([card, normed], out, dims)
    else:
        run(["ffmpeg", "-y", "-i", body, "-c", "copy", out])

    log(f"done -> {out}")
    return out


# --- cli ---------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(prog="vidkit", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transcribe"); t.add_argument("input")
    t.add_argument("-o", "--out", default=None); t.add_argument("--model", default="base.en")
    t.add_argument("--srt", action="store_true")

    ti = sub.add_parser("tighten"); ti.add_argument("input")
    ti.add_argument("-o", "--out", required=True); ti.add_argument("--model", default="base.en")
    ti.add_argument("--max-silence", type=float, default=0.6)

    c = sub.add_parser("captions"); c.add_argument("input")
    c.add_argument("-o", "--out", required=True); c.add_argument("--srt", default=None)
    c.add_argument("--model", default="base.en")

    r = sub.add_parser("reframe"); r.add_argument("input")
    r.add_argument("-o", "--out", required=True); r.add_argument("--aspect", default="9:16", choices=ASPECTS)

    p = sub.add_parser("pipeline"); p.add_argument("input")
    p.add_argument("-o", "--out", required=True); p.add_argument("--aspect", default="9:16", choices=ASPECTS)
    p.add_argument("--title", default=None); p.add_argument("--model", default="base.en")
    p.add_argument("--max-silence", type=float, default=0.6)

    a = ap.parse_args()

    if a.cmd == "transcribe":
        words = transcribe_words(a.input, a.model)
        if a.srt:
            text = words_to_srt(words)
            out = a.out or os.path.splitext(a.input)[0] + ".srt"
        else:
            text = json.dumps(words, indent=2)
            out = a.out or os.path.splitext(a.input)[0] + ".words.json"
        with open(out, "w") as f:
            f.write(text)
        print(out)

    elif a.cmd == "tighten":
        words = transcribe_words(a.input, a.model)
        dur = probe_duration(a.input)
        spans = keep_segments(words, dur, max_silence=a.max_silence)
        cut_to_segments(a.input, spans, a.out)
        kept = sum(b - x for x, b in spans)
        print(f"{dur:.1f}s -> {kept:.1f}s ({len(spans)} spans) -> {a.out}")

    elif a.cmd == "captions":
        srt = a.srt
        tmp = None
        if not srt:
            words = transcribe_words(a.input, a.model)
            tmp = tempfile.mkdtemp(prefix="vidkit_")
            srt = os.path.join(tmp, "cap.srt")
            with open(srt, "w") as f:
                f.write(words_to_srt(words))
        burn_captions(a.input, srt, a.out)
        print(a.out)

    elif a.cmd == "reframe":
        reframe(a.input, a.out, a.aspect)
        print(a.out)

    elif a.cmd == "pipeline":
        pipeline(a.input, a.out, aspect=a.aspect, title=a.title,
                 model_size=a.model, max_silence=a.max_silence)
        print(a.out)


if __name__ == "__main__":
    main()
