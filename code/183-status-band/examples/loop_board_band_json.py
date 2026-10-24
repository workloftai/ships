"""The feed we run: our Loop board's band_json(), as added to loop_board.py.

Shown for reference. fetch_* read our Supabase-backed todo table; swap them for
your own source. The contract is the JSON this prints.
"""
import json


def band_json(fetch_loop_items, fetch_blocked, fetch_overdue, board_compact) -> str:
    items = fetch_loop_items("open") + fetch_loop_items("in_progress")
    blocked = fetch_blocked()
    overdue = fetch_overdue()
    counts = {"research": 0, "ship": 0, "publish": 0}
    for r in items:
        st = r.get("stage") or "research"
        counts[st] = counts.get(st, 0) + 1
    segs = [{"label": k, "value": counts.get(k, 0), "alert": False}
            for k in ("research", "ship", "publish")]
    segs.append({"label": "blocked", "value": len(blocked), "alert": len(blocked) > 0})
    segs.append({"label": "overdue", "value": len(overdue), "alert": len(overdue) > 0})
    return json.dumps({"title": "LOOP", "segments": segs, "detail": board_compact()})
