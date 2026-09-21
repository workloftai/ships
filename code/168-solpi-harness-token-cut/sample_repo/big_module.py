"""Bridge between wlft-post drafts (on disk) and Typefully.

Direction A — push:
    push_draft_from_disk(channel, slug, publish_at, with_hero=True)
        → reads /home/workloft/posts/drafts/<date>-<channel>-<slug>.md
        → uploads hero (if present) to Typefully media
        → POSTs draft with platforms[<channel>].enabled=True
        → records {typefully_draft_id: {channel, slug}} in scheduled.json
        → returns the draft_id

Direction B — pull / reconcile (cron):
    reconcile_published()
        → for each scheduled draft_id we haven't matched yet, look it up in
          Typefully's analytics/{platform}/posts; if it has a URL, call
          wlft-post mark-posted (moves draft → posted/ + writes the ledger row).
        → leaves the scheduled.json entry in place but marks "logged: true" so
          we don't double-log; cleanup happens after 30 days.

The Typefully `draft_title` is set to "<channel>:<slug>" so the draft is
identifiable in Typefully's UI and on lookup.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

from . import client as tf  # noqa: E402

# HARD RULE (Alfred, 2026-07-28): a social post exists to drive traffic to the
# website, so it MUST carry a live workloft.ai article link. A №64 X post once sat
# pointing at a 404 for 3 days because the article was never published. We schedule
# these, so the check is on us: refuse to push a draft whose article link isn't 200.
_WL_URL = re.compile(r"https?://(?:www\.)?workloft\.ai/\S+", re.I)


def _article_link_live(body: str) -> tuple[bool, str]:
    """Return (ok, detail). ok iff the body carries a workloft.ai link that 200s."""
    urls = [u.rstrip(").,;\"'>]}") for u in _WL_URL.findall(body)]
    if not urls:
        return False, "no workloft.ai article link in the post body"
    for url in urls:
        live = False
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(url, method=method,
                                             headers={"User-Agent": "workloft-bridge/1.0"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    live = (r.status == 200)
                break
            except urllib.error.HTTPError as e:
                if e.code == 405 and method == "HEAD":
                    continue
                return False, f"{url} returned HTTP {e.code}"
            except Exception as e:
                return False, f"{url} unreachable: {e}"
        if not live:
            return False, f"{url} is not live (200)"
    return True, "ok"


DRAFTS_DIR = Path("/home/workloft/posts/drafts")
POSTED_DIR = Path("/home/workloft/posts/posted")
STATE_FILE = Path("/home/workloft/typefully/scheduled.json")

# Map our channel names → Typefully's platform keys (they happen to match).
# Threads removed 2026-06-17 (per Alfred — Typefully's Threads connector
# requires an Instagram login we don't want to use). Distribute to X,
# LinkedIn, Bluesky or Mastodon instead.
PLATFORM = {"linkedin": "linkedin", "x": "x", "bluesky": "bluesky",
            "mastodon": "mastodon"}


def _state_load() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text() or "{}")
    except json.JSONDecodeError:
        return {}


def _state_save(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def _parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    block = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    fm: dict = {}
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm, body


def _find_draft(channel: str, slug: str) -> Path | None:
    for d in (DRAFTS_DIR, POSTED_DIR):
        for p in d.glob(f"*-{channel}-{slug}.md"):
            return p
    return None


def push_draft_from_disk(channel: str, slug: str, *,
                          publish_at: str | None = None,
                          with_hero: bool = True) -> dict:
    """Push a wlft-post draft to Typefully.

    publish_at: ISO-8601 with timezone, the literal "now", or "next-free-slot".
                RULE (locked 2026-06-09, Alfred): nothing is ever left in the
                Typefully Drafts tab — every push gets a slot. None, "auto" and
                "unscheduled" all resolve to the next rule-correct slot for the
                channel (LinkedIn Mon-Fri, one per channel per day) — see
                schedule_rules. There is deliberately NO way to create a bare
                unscheduled draft through this function.
    """
    if channel not in PLATFORM:
        raise ValueError(f"channel must be one of {list(PLATFORM)}")
    if publish_at in (None, "auto", "unscheduled"):
        from . import schedule_rules
        publish_at = schedule_rules.next_slot(channel)
    p = _find_draft(channel, slug)
    if p is None:
        raise FileNotFoundError(f"no draft for {channel}/{slug}")
    if p.parent == POSTED_DIR:
        raise RuntimeError(f"draft already posted: {p}")

    fm, body = _parse_front_matter(p.read_text())
    status = fm.get("status", "draft")
    if status != "draft":
        raise RuntimeError(f"draft status is '{status}', refusing to push: {p}")
    body = body.strip()
    if not body:
        raise RuntimeError(f"draft has no body: {p}")

    # HARD: never queue a post whose website article link isn't live (200).
    ok, detail = _article_link_live(body)
    if not ok:
        raise RuntimeError(
            f"refusing to push {channel}/{slug}: {detail}. "
            f"Every social must link to a LIVE workloft.ai article "
            f"(publish the article first, verify 200, then queue)."
        )

    post: dict = {"text": body}
    hero = fm.get("hero_path")
    if with_hero and hero and Path(hero).is_file():
        post["media_ids"] = [tf.upload_media(hero)]

    platforms = {PLATFORM[channel]: {"enabled": True, "posts": [post]}}
    resp = tf.create_draft(
        platforms,
        draft_title=f"{channel}:{slug}",
        publish_at=publish_at,
    )
    draft_id = resp.get("id") or resp.get("draft_id")
    if not draft_id:
        raise RuntimeError(f"Typefully response missing draft id: {resp}")

    state = _state_load()
    state[str(draft_id)] = {
        "channel": channel,
        "slug": slug,
        "publish_at": publish_at,
        "pushed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "logged": False,
    }
    _state_save(state)
    return {"draft_id": draft_id, "channel": channel, "slug": slug,
            "publish_at": publish_at, "draft_path": str(p),
            "with_hero": "media_ids" in post}


def _mark_posted(channel: str, slug: str, url: str) -> tuple[int, str, str]:
    """Run wlft-post mark-posted, which moves draft → posted/ and writes
    the workloft_posts ledger row. Returns (rc, stdout, stderr)."""
    r = subprocess.run(
        ["/usr/local/bin/wlft-post", "mark-posted",
         "--channel", channel, "--slug", slug, "--url", url],
        capture_output=True, text=True,
    )
    return r.returncode, r.stdout, r.stderr


def reconcile_published() -> dict:
    """For every scheduled draft we haven't logged yet, ask Typefully for the
    draft and check the platform-specific published URL fields (e.g.
    `linkedin_published_url`, `x_published_url`). If set, the post is live —
    call wlft-post mark-posted to update both disk + ledger. Idempotent.

    Note: the analytics endpoint (/analytics/{platform}/posts) only supports X
    and requires a date range. The per-draft GET endpoint works for ALL
    platforms and exposes the published URL directly, so we use that."""
    state = _state_load()
    if not state:
        return {"checked": 0, "logged": 0, "still_pending": 0}

    logged = 0
    still = 0
    checked = 0
    for raw_id, meta in list(state.items()):
        if meta.get("logged"):
            continue
        checked += 1
        try:
            did = int(raw_id)
        except ValueError:
            continue
        channel = meta["channel"]
        slug = meta["slug"]
        plat = PLATFORM.get(channel)
        if plat is None:
            # Legacy/disabled channel (e.g. 'threads', removed 2026-06-17). Skip
            # rather than KeyError — that crash was the real cause of the ledger
            # drifting from Typefully (every 15-min reconcile died on a threads row).
            continue
        url_field = f"{plat}_published_url"
        try:
            draft = tf.get_draft(did)
        except Exception as e:
            print(f"WARN: get_draft({did}) failed: {e}", file=sys.stderr)
            still += 1
            continue
        url = draft.get(url_field)
        if not url:
            still += 1
            continue
        rc, out, err = _mark_posted(channel, slug, url)
        if rc == 0:
            meta["logged"] = True
            meta["posted_url"] = url
            meta["posted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            state[raw_id] = meta
            logged += 1
            print(f"✓ logged typefully:{did} → {channel}/{slug} → {url}")
        else:
            print(f"WARN: mark-posted failed for {channel}/{slug}: {err.strip() or out.strip()}",
                  file=sys.stderr)
            still += 1

    # Prune entries older than 30d that have been logged.
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for raw_id in list(state.keys()):
        m = state[raw_id]
        if not m.get("logged"):
            continue
        try:
            ts = datetime.fromisoformat(m.get("posted_at", ""))
        except ValueError:
            continue
        if ts < cutoff:
            del state[raw_id]

    _state_save(state)
    return {"checked": checked, "logged": logged, "still_pending": still,
            "total_in_state": len(state)}
"""Thin Bearer-auth wrapper around the Typefully public API (v2).

Docs: https://typefully.com/docs/api
Auth: Authorization: Bearer <TYPEFULLY_API_KEY>

Only the endpoints we actually use:
- GET    /v2/social-sets
- POST   /v2/social-sets/{id}/drafts
- GET    /v2/social-sets/{id}/drafts/{draft_id}
- GET    /v2/social-sets/{id}/queue
- GET    /v2/social-sets/{id}/analytics/{platform}/posts
- POST   /v2/social-sets/{id}/media/upload   (returns presigned S3 upload_url)
- GET    /v2/social-sets/{id}/media/{media_id}
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib import request as urlrequest, error as urlerror, parse as urlparse

BASE = "https://api.typefully.com"


def _load_env_file(path: str) -> dict[str, str]:
    if not Path(path).exists():
        return {}
    txt = Path(path).read_text()
    return dict(re.findall(r"^([A-Z_]+)=(.*)$", txt, re.M))


def _api_key() -> str:
    k = os.environ.get("TYPEFULLY_API_KEY")
    if not k:
        env = _load_env_file("/home/workloft/conexus/.env")
        k = env.get("TYPEFULLY_API_KEY", "").strip().strip('"')
    if not k:
        raise RuntimeError(
            "TYPEFULLY_API_KEY not set. Generate one at "
            "https://typefully.com/ → Settings → API → Create key, then add "
            "TYPEFULLY_API_KEY=... to /home/workloft/conexus/.env"
        )
    return k


def _social_set_id() -> int:
    raw = os.environ.get("TYPEFULLY_SOCIAL_SET_ID")
    if not raw:
        env = _load_env_file("/home/workloft/conexus/.env")
        raw = env.get("TYPEFULLY_SOCIAL_SET_ID", "").strip().strip('"')
    if not raw:
        raise RuntimeError(
            "TYPEFULLY_SOCIAL_SET_ID not set. Run `wlft-post typefully-setup` "
            "to list your social sets, then add TYPEFULLY_SOCIAL_SET_ID=<id> "
            "to /home/workloft/conexus/.env"
        )
    return int(raw)


def _req(method: str, path: str, *, body: object | None = None,
         timeout: int = 30) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urlrequest.Request(f"{BASE}{path}", data=data, method=method,
                              headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urlerror.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"Typefully {method} {path} → {e.code}: {body}")


def list_social_sets() -> list[dict]:
    return _req("GET", "/v2/social-sets").get("results", [])


def create_draft(platforms: dict, *, draft_title: str | None = None,
                 publish_at: str | None = None,
                 tags: list[str] | None = None,
                 share: bool = False) -> dict:
    """publish_at: ISO-8601, the literal "now", or "next-free-slot".
       Omit to leave as an unscheduled draft.

       platforms shape (only include platforms you want enabled):
         {"linkedin": {"enabled": True, "posts": [{"text": "...",
                                                    "media_ids": []}]}}
    """
    body: dict = {"platforms": platforms, "share": share}
    if draft_title:
        body["draft_title"] = draft_title
    if publish_at:
        body["publish_at"] = publish_at
    if tags:
        body["tags"] = tags
    return _req("POST", f"/v2/social-sets/{_social_set_id()}/drafts", body=body)


def get_draft(draft_id: int) -> dict:
    return _req("GET",
                 f"/v2/social-sets/{_social_set_id()}/drafts/{draft_id}")


def delete_draft(draft_id: int) -> dict:
    """Delete a draft (scheduled or unscheduled). Returns {} on success.
    Verified against the v2 API 2026-06-25."""
    return _req("DELETE",
                f"/v2/social-sets/{_social_set_id()}/drafts/{draft_id}")


def get_queue(start_date: str | None = None, end_date: str | None = None) -> dict:
    """start_date / end_date: YYYY-MM-DD; defaults to today → today+30d."""
    from datetime import date, timedelta
    sd = start_date or date.today().isoformat()
    ed = end_date or (date.today() + timedelta(days=30)).isoformat()
    q = urlparse.urlencode({"start_date": sd, "end_date": ed})
    return _req("GET", f"/v2/social-sets/{_social_set_id()}/queue?{q}")


def list_published(platform: str, *, limit: int = 50,
                    start_date: str | None = None,
                    end_date: str | None = None) -> list[dict]:
    """platform is one of: x, linkedin, threads, bluesky, mastodon.

    Defaults: last 90 days back to today. Analytics endpoint requires
    a date window; we only care about posts that just published since
    the last reconcile, so a recent window is fine."""
    from datetime import date, timedelta
    sd = start_date or (date.today() - timedelta(days=90)).isoformat()
    ed = end_date or date.today().isoformat()
    q = urlparse.urlencode({"limit": limit, "start_date": sd, "end_date": ed})
    path = f"/v2/social-sets/{_social_set_id()}/analytics/{platform}/posts?{q}"
    return _req("GET", path).get("results", [])


def upload_media(file_path: str | Path) -> str:
    """Two-step: ask Typefully for a presigned URL, PUT bytes to it,
    poll until media is 'ready'. Returns the media_id."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(p)
    init = _req("POST",
                 f"/v2/social-sets/{_social_set_id()}/media/upload",
                 body={"file_name": p.name})
    media_id = init["media_id"]
    upload_url = init["upload_url"]

    body = p.read_bytes()
    # Typefully presigns the S3 PUT with an EMPTY Content-Type. urllib otherwise
    # auto-adds "Content-Type: application/x-www-form-urlencoded" whenever data
    # is set, which changes S3's StringToSign and fails the V2 signature check
    # (403 SignatureDoesNotMatch). Force the Content-Type back to empty so it
    # matches what Typefully signed. The x-amz-meta-* values stay in the query
    # string; S3 reads them from there, so we do not resend them as headers.
    put = urlrequest.Request(upload_url, data=body, method="PUT")
    put.add_unredirected_header("Content-Type", "")
    try:
        with urlrequest.urlopen(put, timeout=120) as _r:
            _r.read()
    except urlerror.HTTPError as e:
        raise RuntimeError(f"Typefully media PUT → {e.code}: "
                            f"{e.read().decode('utf-8','ignore')}")

    # Poll until ready (status: processing → ready / failed)
    deadline = time.time() + 60
    while time.time() < deadline:
        info = _req("GET",
                     f"/v2/social-sets/{_social_set_id()}/media/{media_id}")
        status = (info.get("status") or "").lower()
        if status == "ready":
            return media_id
        if status == "failed":
            raise RuntimeError(f"Typefully media {media_id} failed: {info}")
        time.sleep(1)
    raise TimeoutError(f"Typefully media {media_id} still not ready after 60s")
"""Posting-cadence rules for the Workloft Typefully queue.

Rules (updated 2026-06-09, per Alfred — added Mon + Fri to LinkedIn):
  * LinkedIn posts go out Monday-Friday (weekdays).
  * X and Bluesky can post any day of the week (Mon-Sun).
  * One post per channel per day (X, LinkedIn, Bluesky are independent channels).
  * News articles jump the queue ahead of Notes/Ships so they land while still
    fresh; among News the most recent goes soonest.

This module is the single source of truth for those rules. `reorder()` is
idempotent and self-healing: run it any time (after a push, on a cron) and the
live queue is normalised back onto the rules regardless of how items were
scheduled. `next_slot()` gives the schedule step a rule-correct time up front.

Channel times are fixed per channel so a day can carry one of each without
collisions.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from . import client as tf

# Mon=0 .. Sun=6. LinkedIn = Mon-Fri (weekdays); the rest any day.
# Threads removed 2026-06-17 (per Alfred — Typefully's Threads connector needs
# an Instagram login we don't want to use). X / LinkedIn / Bluesky / Mastodon only.
POSTING_WEEKDAYS = {
    "x": (0, 1, 2, 3, 4, 5, 6),
    "bluesky": (0, 1, 2, 3, 4, 5, 6),
    "linkedin": (0, 1, 2, 3, 4),
    "mastodon": (0, 1, 2, 3, 4, 5, 6),
}
# UTC time-of-day per channel (one slot each per posting day)
CHANNEL_TIME_UTC = {"x": (11, 0), "bluesky": (13, 0),
                    "mastodon": (14, 0), "linkedin": (16, 0)}
NEWS_DIR = Path("/home/workloft/workloft-site/labs/news")

_SLUG_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})$")


def is_news(slug: str) -> bool:
    """A post is News iff its article lives in the Labs news directory."""
    return (NEWS_DIR / f"{slug}.html").is_file()


def _slug_date(slug: str) -> str:
    m = _SLUG_DATE.search(slug)
    return m.group(1) if m else "0000-00-00"


def channel_of(draft: dict) -> str | None:
    for ch in ("x", "linkedin", "bluesky", "mastodon"):
        if draft.get(f"{ch}_post_enabled"):
            return ch
    return None


def slug_of(draft: dict) -> str:
    title = draft.get("draft_title") or ""
    return title.split(":", 1)[1] if ":" in title else title


def _posting_dates(start: dt.date, channel: str):
    """Yield successive posting dates for `channel` on/after `start`, forever."""
    days = POSTING_WEEKDAYS[channel]
    d = start
    while True:
        if d.weekday() in days:
            yield d
        d += dt.timedelta(days=1)


def _slot_dt(d: dt.date, channel: str) -> dt.datetime:
    h, m = CHANNEL_TIME_UTC[channel]
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=dt.timezone.utc)


def _scheduled_items(days: int = 60) -> list[dict]:
    """Flat list of live-queue items: {id, channel, slug, at(datetime)}.
    Skips empty schedule slots (draft is None)."""
    today = dt.date.today()
    q = tf.get_queue(start_date=today.isoformat(),
                     end_date=(today + dt.timedelta(days=days)).isoformat())
    out = []
    for day in q.get("days", []):
        for it in (day.get("items") or []):
            dr = it.get("draft")
            if not dr:
                continue
            ch = channel_of(dr)
            if not ch:
                continue
            out.append({
                "id": dr["id"],
                "channel": ch,
                "slug": slug_of(dr),
                "at": dt.datetime.fromisoformat(it["at"].replace("Z", "+00:00")),
            })
    return out


def _first_posting_date(channel: str) -> dt.date:
    """Next posting day for `channel` strictly in the future (tomorrow at the
    earliest), so we never disturb posts already scheduled for today."""
    return next(_posting_dates(dt.date.today() + dt.timedelta(days=1), channel))


def next_slot(channel: str) -> str:
    """ISO-8601 (UTC 'Z') for the next free posting slot for `channel`:
    the earliest future posting day with no post already on that channel."""
    taken = {i["at"].date() for i in _scheduled_items() if i["channel"] == channel}
    for d in _posting_dates(_first_posting_date(channel), channel):
        if d not in taken:
            return _slot_dt(d, channel).strftime("%Y-%m-%dT%H:%M:%SZ")


def plan(items: list[dict] | None = None) -> list[dict]:
    """Compute the desired (id → target datetime) layout without applying it.

    Only items scheduled from tomorrow onward are reflowed; anything already due
    today/sooner is left untouched. Per channel: News first (most recent
    slug-date soonest), then the rest in their current order, laid onto
    consecutive posting days for that channel.
    """
    if items is None:
        items = _scheduled_items()
    cutoff = dt.date.today() + dt.timedelta(days=1)
    out: list[dict] = []
    for channel in ("x", "linkedin", "bluesky", "mastodon"):
        ch_items = [i for i in items
                    if i["channel"] == channel and i["at"].date() >= cutoff]
        news = sorted((i for i in ch_items if is_news(i["slug"])),
                      key=lambda i: _slug_date(i["slug"]), reverse=True)
        if channel == "linkedin":
            # Newest first: fresh items land while still topical; the stale
            # tail drains via the overflow rule instead of blocking the queue.
            rest = sorted((i for i in ch_items if not is_news(i["slug"])),
                          key=lambda i: (_slug_date(i["slug"]), i["at"]),
                          reverse=True)
        else:
            rest = sorted((i for i in ch_items if not is_news(i["slug"])),
                          key=lambda i: i["at"])
        ordered = news + rest
        dates = _posting_dates(_first_posting_date(channel), channel)
        for item in ordered:
            target = _slot_dt(next(dates), channel)
            out.append({**item, "target": target,
                        "news": is_news(item["slug"])})
    return out


def reorder(dry_run: bool = False) -> list[dict]:
    """Apply `plan()` to the live queue via PATCH. Idempotent. Returns the list
    of changes actually made (or that would be made when dry_run)."""
    changes = []
    ssid = tf._social_set_id()
    for p in plan():
        if p["at"] == p["target"]:
            continue
        when = p["target"].strftime("%Y-%m-%dT%H:%M:%SZ")
        changes.append({"id": p["id"], "channel": p["channel"],
                        "slug": p["slug"],
                        "from": p["at"].strftime("%Y-%m-%d %H:%MZ"),
                        "to": p["target"].strftime("%a %Y-%m-%d %H:%MZ"),
                        "news": p["news"]})
        if not dry_run:
            tf._req("PATCH", f"/v2/social-sets/{ssid}/drafts/{p['id']}",
                    body={"publish_at": when})
    return changes
