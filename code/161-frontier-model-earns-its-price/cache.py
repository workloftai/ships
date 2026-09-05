"""
Semantic response cache in front of the tier router.

Repetitive agent workloads (recurring reports, check-ins, the same FAQ asked ten
ways) re-ask near-identical questions. Serving those from cache eliminates the
LLM call entirely — a bigger lever than provider-side prompt caching for repeat
traffic, and it stacks on top of it.

Two-stage match, cheap → precise:
  1. exact match on the NORMALISED prompt (lowercased, depunctuated, whitespace
     collapsed) — high precision, catches trivial rewordings.
  2. cosine similarity over token-count vectors, above SIMILARITY_THRESHOLD —
     catches paraphrases that share vocabulary.

The similarity function is pluggable via `set_embedder`. The default is lexical
(bag-of-words), which is honest about its limits: it catches shared-vocabulary
paraphrases, not deep semantic equivalence. Swap in the fleet's BGE-small
embedder for true semantic matching without touching callers.

Backed by the same SQLite state.db as the circuit breaker. Entries carry a TTL
so stale answers (prices, hours, anything time-sensitive) expire.
"""

import math
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path

DB_PATH = "/var/lib/larry-bob/state.db"
SIMILARITY_THRESHOLD = 0.92   # cosine; deliberately high to avoid wrong hits
DEFAULT_TTL_SECONDS = 24 * 3600


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def _lexical_vector(text: str) -> Counter:
    return Counter(normalise(text).split())


# Pluggable embedder: text -> vector (Counter or list of floats). Default lexical.
_embedder = _lexical_vector


def set_embedder(fn):
    """Swap the similarity backend (e.g. BGE-small). fn: str -> vector."""
    global _embedder
    _embedder = fn


def _cosine(a, b) -> float:
    if isinstance(a, Counter):
        keys = set(a) | set(b)
        dot = sum(a[k] * b[k] for k in keys)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
    else:  # dense vectors
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def init_cache(db_path: str = DB_PATH):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS response_cache (
            id INTEGER PRIMARY KEY,
            norm_prompt TEXT NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            created_ts INTEGER NOT NULL,
            expires_ts INTEGER NOT NULL,
            hits INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_norm ON response_cache(norm_prompt)")
    conn.commit()
    conn.close()


def store(prompt: str, response: str, ttl: int = DEFAULT_TTL_SECONDS,
          db_path: str = DB_PATH):
    now = int(time.time())
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO response_cache (norm_prompt, prompt, response, created_ts, expires_ts) "
        "VALUES (?, ?, ?, ?, ?)",
        (normalise(prompt), prompt, response, now, now + ttl),
    )
    conn.commit()
    conn.close()


def check(prompt: str, db_path: str = DB_PATH):
    """
    Return a cached response for a semantically-matching, unexpired prompt, or
    None. On a hit, increments the hit counter. Returns a dict with the response
    and match metadata so the caller can log cache effectiveness.
    """
    now = int(time.time())
    norm = normalise(prompt)
    conn = sqlite3.connect(db_path)

    # stage 1: exact normalised match (most recent, unexpired)
    row = conn.execute(
        "SELECT id, response FROM response_cache "
        "WHERE norm_prompt = ? AND expires_ts > ? ORDER BY created_ts DESC LIMIT 1",
        (norm, now),
    ).fetchone()
    if row:
        conn.execute("UPDATE response_cache SET hits = hits + 1 WHERE id = ?", (row[0],))
        conn.commit()
        conn.close()
        return {"response": row[1], "match": "exact", "similarity": 1.0}

    # stage 2: cosine similarity over unexpired entries
    qvec = _embedder(prompt)
    best, best_sim = None, 0.0
    for cid, cprompt, cresp in conn.execute(
        "SELECT id, prompt, response FROM response_cache WHERE expires_ts > ?", (now,)
    ):
        sim = _cosine(qvec, _embedder(cprompt))
        if sim > best_sim:
            best, best_sim = (cid, cresp), sim
    if best and best_sim >= SIMILARITY_THRESHOLD:
        conn.execute("UPDATE response_cache SET hits = hits + 1 WHERE id = ?", (best[0],))
        conn.commit()
        conn.close()
        return {"response": best[1], "match": "semantic", "similarity": round(best_sim, 3)}

    conn.close()
    return None


def purge_expired(db_path: str = DB_PATH) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.execute("DELETE FROM response_cache WHERE expires_ts <= ?", (int(time.time()),))
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


if __name__ == "__main__":
    import os
    import tempfile

    db = os.path.join(tempfile.gettempdir(), "test_cache.db")
    if os.path.exists(db):
        os.unlink(db)
    init_cache(db)
    ok = 0

    # miss on empty cache
    ok += check("What are your opening hours?", db) is None
    print("[%s] empty cache -> miss" % ("OK " if check("x", db) is None else "FAIL"))

    store("What are your opening hours?", "We open 9-5, Mon-Fri.", db_path=db)

    # exact-normalised hit (punctuation / case differ)
    r = check("what are your opening hours", db)
    good = r and r["match"] == "exact"
    ok += bool(good)
    print(f"[{'OK ' if good else 'FAIL'}] normalised exact hit -> {r}")

    # near-duplicate hit via the cosine path (shared vocabulary, one extra word).
    # NOTE: the lexical default only catches near-dups; a loose paraphrase like
    # "reset the account password" scores ~0.86 and correctly MISSES. Swap in a
    # real embedder (set_embedder) for true paraphrase matching.
    store("How do I reset my account password?", "Click 'Forgot password' on the login page.", db_path=db)
    r = check("How do I reset my account password please", db)
    good = r is not None and r["match"] == "semantic"
    ok += bool(good)
    print(f"[{'OK ' if good else 'FAIL'}] near-dup cosine hit -> {r}")

    # unrelated query -> miss
    r = check("What is the capital of France?", db)
    good = r is None
    ok += bool(good)
    print(f"[{'OK ' if good else 'FAIL'}] unrelated -> miss ({r})")

    # TTL expiry
    store("temporary fact", "expires now", ttl=-1, db_path=db)
    r = check("temporary fact", db)
    good = r is None
    ok += bool(good)
    print(f"[{'OK ' if good else 'FAIL'}] expired entry -> miss ({r})")

    print(f"\n{ok}/5 passed")
    os.unlink(db)
    raise SystemExit(0 if ok == 5 else 1)
