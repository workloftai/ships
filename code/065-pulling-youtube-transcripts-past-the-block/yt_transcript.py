#!/usr/bin/env python3
"""yt-transcript — pull a YouTube transcript from a link, IP-block resilient.

Usage:
    yt-transcript "https://youtu.be/VIDEOID"
    yt-transcript VIDEOID --json

Tries, in order:
  1. youtube-transcript-api  (works only if this host isn't IP-blocked)
  2. Invidious caption API    (several public instances)
  3. Supadata API            (reliable backstop, needs SUPADATA_API_KEY)

Reads SUPADATA_API_KEY from env or /home/workloft/conexus/.env.
Prints the plain-text transcript to stdout. Exit 0 on success, 3 if every
route failed (so callers can fall back to asking the user to paste).
"""
from __future__ import annotations
import json, os, re, sys, urllib.parse, urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
INVIDIOUS = [
    "inv.nadeko.net", "iv.melmac.space", "invidious.nerdvpn.de",
    "yewtu.be", "invidious.f5.si", "invidious.privacyredirect.com",
]


def vid_from(arg: str) -> str:
    arg = arg.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", arg):
        return arg
    u = urllib.parse.urlparse(arg)
    if u.hostname and "youtu.be" in u.hostname:
        return u.path.lstrip("/").split("/")[0]
    qs = urllib.parse.parse_qs(u.query)
    if "v" in qs:
        return qs["v"][0]
    m = re.search(r"(?:shorts/|embed/|v/)([A-Za-z0-9_-]{11})", arg)
    if m:
        return m.group(1)
    raise SystemExit(f"Could not extract a video id from: {arg}")


def _get(url: str, headers: dict | None = None, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _load_key() -> str | None:
    k = os.environ.get("SUPADATA_API_KEY")
    if k:
        return k.strip()
    envp = "/home/workloft/conexus/.env"
    try:
        for line in open(envp, encoding="utf-8", errors="ignore"):
            if line.startswith("SUPADATA_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def via_transcript_api(vid: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    api = YouTubeTranscriptApi()
    fetched = api.fetch(vid)
    return " ".join(s.text for s in fetched).strip()


def via_invidious(vid: str) -> str:
    for h in INVIDIOUS:
        try:
            lst = json.loads(_get(f"https://{h}/api/v1/captions/{vid}", timeout=12))
        except Exception:
            continue
        caps = lst.get("captions") or []
        en = next((c for c in caps if c.get("languageCode", "").startswith("en")), None)
        if not en:
            continue
        try:
            raw = _get(f"https://{h}{en['url']}", timeout=20).decode("utf-8", "ignore")
        except Exception:
            continue
        if len(raw) < 40:
            continue
        return _vtt_to_text(raw)
    raise RuntimeError("no invidious instance served the track")


def via_supadata(vid: str, key: str) -> str:
    url = f"https://api.supadata.ai/v1/transcript?url=https://youtu.be/{vid}&text=true"
    data = json.loads(_get(url, headers={"x-api-key": key}, timeout=40))
    txt = data.get("content") or data.get("transcript") or ""
    if isinstance(txt, list):
        txt = " ".join(seg.get("text", "") for seg in txt)
    return txt.strip()


def _vtt_to_text(raw: str) -> str:
    out: list[str] = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if (not ln or ln == "WEBVTT" or "-->" in ln or ln.isdigit()
                or ln.startswith(("Kind:", "Language:", "NOTE"))):
            continue
        ln = re.sub(r"<[^>]+>", "", ln)
        if not out or out[-1] != ln:
            out.append(ln)
    return " ".join(out).strip()


def fetch(vid: str) -> tuple[str, str]:
    routes = [("youtube-transcript-api", via_transcript_api),
              ("invidious", via_invidious)]
    key = _load_key()
    if key:
        routes.append(("supadata", lambda v: via_supadata(v, key)))
    errs = []
    for name, fn in routes:
        try:
            txt = fn(vid)
            if txt and len(txt.split()) > 5:
                return txt, name
            errs.append(f"{name}: empty")
        except Exception as e:
            errs.append(f"{name}: {type(e).__name__}: {str(e)[:80]}")
    raise SystemExit("ALL_ROUTES_FAILED\n  " + "\n  ".join(errs))


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    if not args:
        raise SystemExit("usage: yt-transcript <youtube-url|id> [--json]")
    vid = vid_from(args[0])
    try:
        txt, route = fetch(vid)
    except SystemExit as e:
        if as_json:
            print(json.dumps({"ok": False, "video_id": vid, "error": str(e)}))
        else:
            sys.stderr.write(str(e) + "\n")
        sys.exit(3)
    if as_json:
        print(json.dumps({"ok": True, "video_id": vid, "route": route,
                          "words": len(txt.split()), "transcript": txt}))
    else:
        print(txt)


if __name__ == "__main__":
    main()
