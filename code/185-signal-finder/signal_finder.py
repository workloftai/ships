#!/usr/bin/env python3
"""signal-finder: turn hours of someone talking into one page you can use,
and find one real thing a person said so your opener proves you listened.

Two modes:

  playbook  sources (YouTube URLs, transcript files, text/markdown files, web
            pages) -> chunk -> extract claims per chunk -> one deduplicated
            playbook: principles, steps, quotes with source + timestamp,
            contradictions.

  signal    person + company (+ URLs, or Exa search if EXA_API_KEY is set)
            -> the single strongest, most recent public thing they said,
            one implication, and a ten-second opener.

Hard rules, enforced in code, not just in the prompt:
  * Every quote must appear verbatim in the source text it is attributed to.
    Quotes the model paraphrased or invented are dropped before rendering.
    Timestamps come from where the code found the quote, not from the model.
  * signal mode returns NO opener when no verified signal exists. It never
    falls back to generic "personalisation".
  * Public sources only. It reads what you point it at, nothing behind a login.

Run without any API key:   python3 signal_finder.py demo
Tests:                     python3 -m unittest discover -s tests

Built by Workloft (https://workloft.ai). MIT.
"""
from __future__ import annotations

import argparse
import bisect
import html
import html.parser
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = os.environ.get("SIGNAL_FINDER_MODEL", "claude-opus-5-5")
UA = "Mozilla/5.0 (signal-finder; +https://github.com/workloftai/ships)"
CHUNK_CHARS = 24_000  # roughly 6k tokens per extraction call


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class Segment:
    start: float | None  # seconds into the recording, None for plain text
    text: str


@dataclass
class Source:
    sid: str
    title: str
    url: str | None
    kind: str  # youtube | transcript | text | web
    segments: list[Segment]
    date: str | None = None
    note: str = ""
    _index: tuple | None = field(default=None, repr=False)

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments)

    def link_at(self, seconds: float | None) -> str | None:
        if not self.url:
            return None
        if seconds is not None and self.kind == "youtube":
            sep = "&" if "?" in self.url else "?"
            return f"{self.url}{sep}t={int(seconds)}s"
        return self.url

    # -- verbatim quote check ------------------------------------------------
    def _norm_index(self):
        """Normalised full text plus the offset where each segment starts."""
        if self._index is None:
            parts, starts, pos = [], [], 0
            for seg in self.segments:
                n = normalise(seg.text)
                starts.append(pos)
                parts.append(n)
                pos += len(n) + 1
            self._index = (" ".join(parts), starts)
        return self._index

    def locate(self, quote: str) -> tuple[bool, float | None]:
        """Return (found_verbatim, start_seconds_of_the_segment_it_starts_in)."""
        q = normalise(quote)
        if len(q.split()) < 4:  # too short to prove anything
            return False, None
        full, starts = self._norm_index()
        pos = full.find(q)
        if pos < 0:
            return False, None
        i = max(0, bisect.bisect_right(starts, pos) - 1)
        return True, self.segments[i].start


def normalise(s: str) -> str:
    s = html.unescape(s).lower()
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fmt_ts(seconds: float | None) -> str:
    if seconds is None:
        return ""
    s = int(seconds)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


# --------------------------------------------------------------------------
# Loading sources
# --------------------------------------------------------------------------

YT_RE = re.compile(r"(?:youtu\.be/|v=|shorts/|embed/)([A-Za-z0-9_-]{11})")
TS_LINE = re.compile(r"^\s*[\[(]?((?:\d+:)?\d{1,2}:\d{2})[\])]?\s+(.*)$")
VTT_CUE = re.compile(r"((?:\d+:)?\d{1,2}:\d{2}[.,]\d{3})\s*-->")


def parse_clock(t: str) -> float:
    parts = [float(p.replace(",", ".")) for p in t.split(":")]
    secs = 0.0
    for p in parts:
        secs = secs * 60 + p
    return secs


def parse_transcript_text(raw: str) -> list[Segment]:
    """Handles .vtt/.srt cues, '[mm:ss] text' lines, or plain paragraphs."""
    lines = raw.splitlines()
    if any(VTT_CUE.search(ln) for ln in lines[:50]):
        segs, cur_start, buf = [], None, []
        for ln in lines:
            m = VTT_CUE.search(ln)
            if m:
                if buf:
                    segs.append(Segment(cur_start, " ".join(buf)))
                cur_start, buf = parse_clock(m.group(1)), []
            elif ln.strip() and not ln.strip().isdigit() and not ln.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")):
                buf.append(re.sub(r"<[^>]+>", "", ln.strip()))
        if buf:
            segs.append(Segment(cur_start, " ".join(buf)))
        return dedupe_rolling(segs)
    timed = [TS_LINE.match(ln) for ln in lines if ln.strip()]
    if timed and sum(1 for m in timed if m) >= 0.6 * len(timed):
        return [Segment(parse_clock(m.group(1)), m.group(2)) for m in timed if m]
    paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    return [Segment(None, re.sub(r"\s+", " ", p)) for p in paras]


def dedupe_rolling(segs: list[Segment]) -> list[Segment]:
    """YouTube auto-captions repeat the previous line in each cue."""
    out: list[Segment] = []
    for s in segs:
        if out and s.text.startswith(out[-1].text):
            s = Segment(s.start, s.text[len(out[-1].text):].strip())
        if s.text:
            out.append(s)
    return out


class _TextExtractor(html.parser.HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "noscript", "svg", "form", "aside"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "blockquote", "br", "section", "article", "tr"}

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.out: list[str] = []
        self.title = ""
        self.date = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta" and not self.date:
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key in {"article:published_time", "datepublished", "date", "dc.date", "pubdate", "og:published_time"}:
                self.date = (a.get("content") or "")[:10] or None
        if tag == "time" and not self.date and a.get("datetime"):
            self.date = a["datetime"][:10]
        if tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.depth:
            self.out.append(data)


def http_get(url: str, headers: dict | None = None, data: bytes | None = None, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_web(url: str, sid: str) -> Source:
    raw = http_get(url).decode("utf-8", "replace")
    p = _TextExtractor()
    p.feed(raw)
    text = "".join(p.out)
    paras = [re.sub(r"\s+", " ", t).strip() for t in re.split(r"\n\s*\n", text)]
    segs = [Segment(None, t) for t in paras if len(t) > 1]
    return Source(sid, p.title.strip() or url, url, "web", segs, date=p.date)


# -- pluggable YouTube transcript fetchers ----------------------------------

class TranscriptError(RuntimeError):
    pass


def fetch_youtube(url: str, fetcher: str, lang: str) -> tuple[list[Segment], str]:
    m = YT_RE.search(url)
    if not m:
        raise TranscriptError(f"not a YouTube URL: {url}")
    vid = m.group(1)
    if fetcher == "youtube-transcript-api":
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError as e:
            raise TranscriptError("pip install youtube-transcript-api, or pick another --fetcher") from e
        api = YouTubeTranscriptApi()
        fetched = api.fetch(vid, languages=[lang])
        segs = [Segment(float(s.start), s.text) for s in fetched]
        kind = "auto-generated" if getattr(fetched, "is_generated", False) else "uploaded"
        return segs, f"captions via youtube-transcript-api ({kind}, {getattr(fetched, 'language_code', lang)})"
    if fetcher == "supadata":
        key = os.environ.get("SUPADATA_API_KEY")
        if not key:
            raise TranscriptError("SUPADATA_API_KEY not set")
        q = urllib.parse.urlencode({"url": f"https://youtu.be/{vid}", "text": "false", "lang": lang})
        d = json.loads(http_get(f"https://api.supadata.ai/v1/transcript?{q}", {"x-api-key": key}, timeout=120))
        got = d.get("lang")
        # Auto-dub guard: some videos now default to a machine-dubbed track.
        if got and got != lang:
            raise TranscriptError(f"asked for '{lang}' but got '{got}' (likely an auto-dubbed track); refusing")
        segs = [Segment(c["offset"] / 1000, c["text"].replace("\xa0", " ").replace("\n", " ")) for c in d.get("content", [])]
        return segs, f"captions via Supadata ({got or lang})"
    if fetcher == "cmd":
        tmpl = os.environ.get("SIGNAL_FINDER_TRANSCRIPT_CMD")
        if not tmpl:
            raise TranscriptError("set SIGNAL_FINDER_TRANSCRIPT_CMD, e.g. 'yt-transcript {url}'")
        out = subprocess.run(shlex.split(tmpl.replace("{url}", url)), capture_output=True, text=True, timeout=300).stdout
        first, _, rest = out.partition("\n")
        if first.startswith("SOURCE:"):
            if "metadata" in first.lower():
                raise TranscriptError("fetcher returned metadata only, no transcript")
            out = rest
        return parse_transcript_text(out), "captions via external command"
    raise TranscriptError(f"unknown fetcher {fetcher}")


def youtube_title(url: str) -> str:
    """Public oEmbed lookup for the title and channel. Falls back to the URL."""
    try:
        q = urllib.parse.urlencode({"url": url, "format": "json"})
        d = json.loads(http_get(f"https://www.youtube.com/oembed?{q}", timeout=15))
        return f"{d['title']} ({d.get('author_name', 'YouTube')})".replace(" \u2014 ", ": ")
    except Exception:
        return url


def load_source(spec: str, sid: str, fetcher: str, lang: str) -> Source:
    """spec is a path or URL, optionally suffixed with '|YYYY-MM-DD'."""
    spec, _, d = spec.partition("|")
    d = d.strip() or None
    if re.match(r"https?://", spec):
        if YT_RE.search(spec) and ("youtu" in spec):
            segs, note = fetch_youtube(spec, fetcher, lang)
            return Source(sid, youtube_title(spec), spec, "youtube", segs, date=d, note=note)
        s = load_web(spec, sid)
        s.date = d or s.date
        return s
    p = Path(spec).expanduser()
    raw = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() in {".html", ".htm"}:
        x = _TextExtractor()
        x.feed(raw)
        segs = [Segment(None, re.sub(r"\s+", " ", t).strip()) for t in re.split(r"\n\s*\n", "".join(x.out))]
        return Source(sid, x.title.strip() or p.name, None, "web", [s for s in segs if s.text], date=d or x.date, note="local file")
    segs = parse_transcript_text(raw)
    url = None
    m = re.search(r"^(?:#|NOTE)?\s*source:\s*(https?://\S+)", raw, re.I | re.M)
    if m:
        url = m.group(1)
    title = p.stem
    mt = re.search(r"^(?:#|NOTE)?\s*title:\s*(.+)$", raw, re.I | re.M)
    if mt:
        title = mt.group(1).strip()
    md = re.search(r"^(?:#|NOTE)?\s*date:\s*(\d{4}-\d{2}-\d{2})", raw, re.I | re.M)
    kind = "youtube" if url and YT_RE.search(url) else ("transcript" if segs and segs[0].start is not None else "text")
    return Source(sid, title, url, kind, segs, date=d or (md.group(1) if md else None), note="local file")


def chunk(source: Source, max_chars: int = CHUNK_CHARS) -> list[str]:
    out, buf, size, last_mark = [], [], 0, -999.0
    for seg in source.segments:
        line = seg.text
        if seg.start is not None and seg.start - last_mark >= 30:
            line = f"[{fmt_ts(seg.start)}] {line}"
            last_mark = seg.start
        if size + len(line) > max_chars and buf:
            out.append("\n".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line) + 1
    if buf:
        out.append("\n".join(buf))
    return out


# --------------------------------------------------------------------------
# Model backends
# --------------------------------------------------------------------------

class Claude:
    """Anthropic Messages API with structured JSON output."""

    def __init__(self, model: str, effort: str):
        import anthropic  # pip install anthropic
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.model, self.effort = model, effort
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0

    def json(self, system: str, user: str, schema: dict, effort: str | None = None) -> dict:
        with self.client.messages.stream(
            model=self.model,
            max_tokens=32000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": effort or self.effort,
                           "format": {"type": "json_schema", "schema": schema}},
        ) as stream:
            resp = stream.get_final_message()
        self.calls += 1
        self.tokens_in += resp.usage.input_tokens
        self.tokens_out += resp.usage.output_tokens
        if resp.stop_reason == "refusal":
            raise RuntimeError("model declined this request")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("output hit max_tokens; use smaller chunks")
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)


class Offline:
    """Deterministic heuristics so the whole pipeline runs with no API key.
    Not a model. Good enough to show the shape of the output and to test the
    guards (verbatim check, no-signal path)."""

    calls = tokens_in = tokens_out = 0
    CUES = re.compile(r"\b(you should|you have to|always|never|the key|the trick|my rule|the mistake|start with|don't|stop|instead|i think|i believe|we learned|the lesson)\b", re.I)

    def json(self, system: str, user: str, schema: dict, effort: str | None = None) -> dict:
        task = system.split("\n", 1)[0]
        body = user.split("<<<", 1)[-1].rsplit(">>>", 1)[0]
        if task.startswith("EXTRACT"):
            items = []
            for sent in re.split(r"(?<=[.!?])\s+", re.sub(r"\[\d[\d:]*\]\s*", "", body)):
                sent = sent.strip()
                if self.CUES.search(sent) and 6 <= len(sent.split()) <= 40:
                    kind = "warning" if re.search(r"\b(never|don't|mistake|stop)\b", sent, re.I) else "tactic"
                    items.append({"kind": kind, "statement": sent, "quote": sent})
            return {"items": items[:12]}
        if task.startswith("SYNTHESISE"):
            rows = [ln.split(" | ") for ln in body.strip().splitlines() if ln.count(" | ") >= 4]
            seen, principles, steps, quotes = set(), [], [], []
            for r in rows:
                key = normalise(r[4])[:40]
                if key in seen:
                    continue
                seen.add(key)
                (steps if r[3] == "tactic" else principles).append({"text": r[4], "support": [r[0]]})
                quotes.append(r[0])
            return {"title": "Offline playbook (heuristic, no model)", "summary": "Sentences that look like advice, deduplicated. Run with an API key for a real synthesis.",
                    "principles": principles[:6], "steps": steps[:6], "quotes": quotes[:5], "contradictions": []}
        if task.startswith("SIGNALS"):
            cands = []
            for sent in re.split(r"(?<=[.!?])\s+", body):
                sent = sent.strip()
                if re.search(r"\b(I|we)\b", sent) and self.CUES.search(sent) and 6 <= len(sent.split()) <= 40:
                    cands.append({"quote": sent, "about": sent[:60], "said_by_person": True})
            return {"candidates": cands[:5]}
        if task.startswith("PICK"):
            rows = re.findall(r"^(C\d+) \| [^|]+ \| ([^|]+) \|", body, re.M)
            ids = [r[0] for r in rows]
            if not ids:
                return {"chosen": "NONE", "why": "no candidates", "implication": "", "signal_phrase": ""}
            return {"chosen": ids[0], "why": "most recent candidate (offline heuristic)",
                    "implication": "Offline mode cannot judge implications; run with a model.",
                    "signal_phrase": f"your piece \"{rows[0][1].strip()}\""}
        raise ValueError(task)


# --------------------------------------------------------------------------
# Mode 1: playbook
# --------------------------------------------------------------------------

EXTRACT_SYS = """EXTRACT
You read one chunk of a transcript or article and pull out the reusable ideas: principles, tactics, warnings and claims a practitioner could act on.
Rules:
- 'statement' is your one-line paraphrase in plain British English.
- 'quote' MUST be copied character for character from the chunk (8 to 40 words). Do not fix grammar or transcription errors. If you cannot find an exact supporting quote, use an empty string.
- Skip small talk, ads, intros and anecdotes with no lesson.
- At most 12 items. Fewer is fine."""

EXTRACT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["items"],
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["kind", "statement", "quote"],
        "properties": {
            "kind": {"type": "string", "enum": ["principle", "tactic", "warning", "claim"]},
            "statement": {"type": "string"}, "quote": {"type": "string"}}}}},
}

SYNTH_SYS = """SYNTHESISE
You get a numbered list of ideas extracted from several sources. Merge duplicates and write a one-page playbook.
Rules:
- Every principle and step cites the item ids that support it in 'support'. No support, no line.
- 'quotes' lists 3 to 6 item ids whose quotes best carry the playbook. Pick only ids that have a quote.
- 'contradictions' covers real tensions between items (different sources, or the same speaker at different times), citing both ids. Empty list if none.
- 4 to 8 principles, 3 to 8 steps in a sensible order. Plain British English, no em dashes, no hype."""

SYNTH_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "summary", "principles", "steps", "quotes", "contradictions"],
    "properties": {
        "title": {"type": "string"}, "summary": {"type": "string"},
        "principles": {"type": "array", "items": {"$ref": "#/$defs/line"}},
        "steps": {"type": "array", "items": {"$ref": "#/$defs/line"}},
        "quotes": {"type": "array", "items": {"type": "string"}},
        "contradictions": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["text", "a", "b"],
            "properties": {"text": {"type": "string"}, "a": {"type": "string"}, "b": {"type": "string"}}}},
    },
    "$defs": {"line": {"type": "object", "additionalProperties": False, "required": ["text", "support"],
                       "properties": {"text": {"type": "string"}, "support": {"type": "array", "items": {"type": "string"}}}}},
}


def run_playbook(sources: list[Source], llm, log=print) -> dict:
    items, proposed, dropped = [], 0, 0
    for src in sources:
        for ci, ch in enumerate(chunk(src)):
            log(f"  extract {src.sid} chunk {ci + 1}")
            got = llm.json(EXTRACT_SYS, f"Source: {src.title}\n<<<\n{ch}\n>>>", EXTRACT_SCHEMA, effort="low")
            for it in got.get("items", []):
                q = it.get("quote", "").strip()
                ts, ok = None, False
                if q:
                    proposed += 1
                    ok, ts = src.locate(q)
                    if not ok:
                        dropped += 1
                items.append({"id": f"I{len(items) + 1}", "source": src, "kind": it["kind"],
                              "statement": it["statement"], "quote": " ".join(q.split()) if ok else "", "ts": ts})
    by_id = {i["id"]: i for i in items}
    table = "\n".join(f"{i['id']} | {i['source'].sid} | {fmt_ts(i['ts']) or '-'} | {i['kind']} | {i['statement']} | {i['quote'] or '(no verified quote)'}" for i in items)
    log(f"  synthesise {len(items)} items")
    syn = llm.json(SYNTH_SYS, f"Sources: {', '.join(s.sid + '=' + s.title for s in sources)}\n<<<\n{table}\n>>>", SYNTH_SCHEMA, effort="high")
    # Code-side guard: drop any cited id that does not exist, any quote id without a verified quote.
    for key in ("principles", "steps"):
        syn[key] = [ln for ln in syn[key] if any(s in by_id for s in ln["support"])]
    syn["quotes"] = [q for q in syn["quotes"] if q in by_id and by_id[q]["quote"]]
    syn["contradictions"] = [c for c in syn["contradictions"] if c["a"] in by_id and c["b"] in by_id]
    return {"syn": syn, "items": by_id, "sources": sources,
            "stats": {"items": len(items), "quotes_proposed": proposed, "quotes_dropped": dropped}}


def render_playbook(r: dict) -> str:
    syn, items = r["syn"], r["items"]

    def cite(ids):
        out = []
        for i in ids:
            it = items.get(i)
            if it:
                out.append(f"{it['source'].sid}{' ' + fmt_ts(it['ts']) if it['ts'] is not None else ''}")
        out = list(dict.fromkeys(out))
        return ", ".join(out[:4]) + (f" +{len(out) - 4} more" if len(out) > 4 else "")

    L = [f"# {syn['title']}", "", syn["summary"], "", "## Principles"]
    L += [f"- {p['text']} _({cite(p['support'])})_" for p in syn["principles"]]
    L += ["", "## Steps"]
    L += [f"{n}. {s['text']} _({cite(s['support'])})_" for n, s in enumerate(syn["steps"], 1)]
    L += ["", "## Quotes (checked verbatim against the transcript)"]
    for q in syn["quotes"]:
        it = items[q]
        link = it["source"].link_at(it["ts"])
        where = f"{it['source'].sid} {fmt_ts(it['ts'])}".strip()
        L.append(f"> \"{it['quote']}\"  \n> {f'[{where}]({link})' if link else where}")
        L.append("")
    if syn["contradictions"]:
        L += ["## Contradictions and tensions"]
        L += [f"- {c['text']} _({cite([c['a']])} vs {cite([c['b']])})_" for c in syn["contradictions"]]
        L.append("")
    L += ["## Sources"]
    for s in r["sources"]:
        L.append(f"- **{s.sid}** {s.title}{', ' + s.date if s.date else ''}. {s.url or ''} ({s.note})")
    st = r["stats"]
    L += ["", f"_{st['items']} ideas extracted. {st['quotes_proposed']} quotes proposed by the model, "
              f"{st['quotes_dropped']} dropped because they were not in the source word for word. "
              "Transcripts are machine-made: check a quote against the recording before you repeat it._"]
    return "\n".join(L)


# --------------------------------------------------------------------------
# Mode 2: signal
# --------------------------------------------------------------------------

SIGNALS_SYS = """SIGNALS
You read one public source and find things that {person} ({company}) personally said or wrote: opinions, bets, problems they are working on, lessons. These are 'signals' a stranger could reference to show they actually listened.
Rules:
- Only words {person} said or wrote themselves. Not the host, not other guests, not the article's author unless that is {person}.
- 'quote' MUST be copied character for character from the source (8 to 40 words).
- If {person} does not speak or write in this source, return an empty list. Never guess.
- At most 5 candidates. Prefer specific and opinionated over generic."""

SIGNALS_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["candidates"],
    "properties": {"candidates": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["quote", "about", "said_by_person"],
        "properties": {"quote": {"type": "string"}, "about": {"type": "string"}, "said_by_person": {"type": "boolean"}}}}},
}

PICK_SYS = """PICK
You choose the single strongest signal for a cold opener to {person} ({company}). Strongest = specific, opinionated, and as recent as possible (dates are given; prefer the newest unless an older one is far stronger).
Return:
- 'chosen': the candidate id, or "NONE" if nothing is specific enough to be worth referencing.
- 'why': one sentence.
- 'implication': one sentence on what this suggests they care about right now. No speculation beyond the quote.
- 'signal_phrase': a short phrase that completes "I saw ...", naming the source, e.g. "your talk at X where you said Y". Under 25 words. Address them as 'you'. No em dashes, no flattery."""

PICK_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["chosen", "why", "implication", "signal_phrase"],
    "properties": {"chosen": {"type": "string"}, "why": {"type": "string"},
                   "implication": {"type": "string"}, "signal_phrase": {"type": "string"}},
}


def exa_search(person: str, company: str, n: int = 8) -> list[str]:
    key = os.environ.get("EXA_API_KEY")
    if not key:
        raise RuntimeError("EXA_API_KEY not set; pass --url instead")
    body = json.dumps({"query": f"{person} {company} interview podcast talk or post in their own words",
                       "numResults": n, "type": "auto"}).encode()
    d = json.loads(http_get("https://api.exa.ai/search", {"x-api-key": key, "Content-Type": "application/json"}, data=body))
    return [f"{r['url']}|{(r.get('publishedDate') or '')[:10]}" for r in d.get("results", [])]


def run_signal(person: str, company: str, sources: list[Source], llm, log=print) -> dict:
    last = person.split()[-1].lower()
    cands, notes = [], []
    for src in sources:
        if last not in src.text.lower():
            notes.append(f"{src.sid}: skipped, does not mention {person}")
            continue
        for ci, ch in enumerate(chunk(src)):
            log(f"  scan {src.sid} chunk {ci + 1}")
            sys_p = SIGNALS_SYS.format(person=person, company=company)
            got = llm.json(sys_p, f"Source: {src.title} ({src.date or 'date unknown'})\n<<<\n{ch}\n>>>", SIGNALS_SCHEMA, effort="medium")
            for c in got.get("candidates", []):
                ok, ts = src.locate(c["quote"])
                if not (ok and c.get("said_by_person")):
                    notes.append(f"{src.sid}: dropped a candidate that was not verbatim or not by {person}")
                    continue
                cands.append({"id": f"C{len(cands) + 1}", "source": src, "quote": " ".join(c["quote"].split()), "about": c["about"], "ts": ts})
    result = {"person": person, "company": company, "signal": None, "implication": None, "opener": None,
              "notes": notes, "candidates": len(cands)}
    if not cands:
        result["reason"] = "No verified public signal found. No opener generated."
        return result
    table = "\n".join(f"{c['id']} | {c['source'].date or 'date unknown'} | {c['source'].title} | {c['quote']}" for c in cands)
    pick = llm.json(PICK_SYS.format(person=person, company=company), f"<<<\n{table}\n>>>", PICK_SCHEMA, effort="high")
    chosen = next((c for c in cands if c["id"] == pick["chosen"]), None)
    if not chosen:
        result["reason"] = "Candidates found, but none specific enough to reference. No opener generated."
        return result
    phrase = pick["signal_phrase"].strip().rstrip(".").replace("\u2014", ",")
    first = person.split()[0]
    src = chosen["source"]
    result.update({
        "signal": {"quote": chosen["quote"], "source": src.title, "url": src.link_at(chosen["ts"]),
                   "date": src.date, "timestamp": fmt_ts(chosen["ts"]) or None, "why": pick["why"]},
        "implication": pick["implication"],
        "opener": f"Hey {first}, thanks for connecting. I saw {phrase}, which is exactly what I wanted to ask you about.",
    })
    return result


def render_signal(r: dict) -> str:
    L = [f"# Signal: {r['person']} ({r['company']})", ""]
    if not r["opener"]:
        L += [f"**{r['reason']}**", "", "Nothing here is safe to personalise with. Do not make something up."]
    else:
        s = r["signal"]
        L += ["## Strongest signal", f"> \"{s['quote']}\"", "",
              f"Source: {s['source']}{', ' + s['date'] if s['date'] else ', date unknown'}"
              f"{', at ' + s['timestamp'] if s['timestamp'] else ''}  ", f"{s['url'] or ''}", "",
              f"Why this one: {s['why']}", "", "## Implication", r["implication"], "",
              "## Opener (about ten seconds)", r["opener"], "",
              "_Quote checked word for word against the source. Listen to it yourself before you use it._"]
    if r["notes"]:
        L += ["", "## Notes"] + [f"- {n}" for n in r["notes"]]
    return "\n".join(L)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def make_llm(args):
    if args.offline:
        return Offline()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Use --offline to run the heuristic dry run.")
    return Claude(args.model, args.effort)


def load_all(specs, fetcher, lang, log):
    out = []
    for n, spec in enumerate(specs, 1):
        try:
            out.append(load_source(spec, f"S{n}", fetcher, lang))
            log(f"  loaded S{n}: {out[-1].title} ({len(out[-1].text.split())} words) {out[-1].note}")
        except Exception as e:  # keep going, report it
            log(f"  could not load {spec}: {e}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="signal_finder", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    for name in ("playbook", "signal"):
        p = sub.add_parser(name)
        p.add_argument("--model", default=DEFAULT_MODEL)
        p.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
        p.add_argument("--fetcher", default=os.environ.get("SIGNAL_FINDER_FETCHER", "youtube-transcript-api"),
                       choices=["youtube-transcript-api", "supadata", "cmd"])
        p.add_argument("--lang", default="en", help="transcript language; other tracks are refused")
        p.add_argument("--offline", action="store_true", help="no API calls, heuristic dry run")
        p.add_argument("--json", action="store_true")
        p.add_argument("-o", "--out")
        if name == "playbook":
            p.add_argument("sources", nargs="+", help="YouTube URL, web URL, or file (.txt .md .vtt .srt .html)")
        else:
            p.add_argument("person")
            p.add_argument("company")
            p.add_argument("--url", action="append", default=[], help="public source; 'URL|YYYY-MM-DD' to set a date")
            p.add_argument("--search", choices=["none", "exa"], default="none")
    sub.add_parser("demo", help="run both modes offline on the bundled fixtures")
    args = ap.parse_args(argv)
    log = lambda m: print(m, file=sys.stderr)

    if args.mode == "demo":
        fx = HERE / "fixtures"
        a = argparse.Namespace(offline=True)
        llm = make_llm(a)
        print(render_playbook(run_playbook(load_all([str(fx / "sample-talk.vtt"), str(fx / "sample-post.md")], "cmd", "en", log), llm, log)))
        print("\n" + "-" * 60 + "\n")
        srcs = load_all([str(fx / "sample-post.md"), str(fx / "sample-talk.vtt")], "cmd", "en", log)
        print(render_signal(run_signal("Sam Example", "Example Labs", srcs, llm, log)))
        print("\n" + "-" * 60 + "\n")
        print(render_signal(run_signal("Nobody Real", "Nowhere Ltd", srcs, llm, log)))
        return 0

    llm = make_llm(args)
    if args.mode == "playbook":
        srcs = load_all(args.sources, args.fetcher, args.lang, log)
        if not srcs:
            sys.exit("no sources loaded")
        r = run_playbook(srcs, llm, log)
        out = json.dumps({"playbook": r["syn"], "stats": r["stats"]}, indent=2) if args.json else render_playbook(r)
        code = 0
    else:
        specs = list(args.url)
        if args.search == "exa":
            specs += exa_search(args.person, args.company)
        srcs = load_all(specs, args.fetcher, args.lang, log)
        r = run_signal(args.person, args.company, srcs, llm, log)
        out = json.dumps({k: v for k, v in r.items()}, indent=2, default=str) if args.json else render_signal(r)
        code = 0 if r["opener"] else 3
    log(f"  model calls: {llm.calls}, tokens in/out: {llm.tokens_in}/{llm.tokens_out}")
    if args.out:
        Path(args.out).write_text(out + "\n")
    print(out)
    return code


if __name__ == "__main__":
    sys.exit(main())
