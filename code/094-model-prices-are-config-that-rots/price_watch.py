#!/usr/bin/env python3
"""Price watch — diff Ruby's catalogue against the OpenRouter Models API.

The June 2026 OpenRouter drop added a Models API (programmatic catalogue:
price, context, modality per model). This script pulls it and diffs every
`provider: openrouter` entry in models.yaml against the live numbers, so
price cuts (DeepSeek V4-flash fell 36% in June) and price RISES (Kimi K2.7
rose 21%) surface as a report instead of silently rotting the cost model.

Usage:
    python3 price_watch.py            # human report
    python3 price_watch.py --json     # machine-readable
Exit codes: 0 = catalogue matches live, 1 = drift found, 2 = fetch failed.

Only checks openrouter-provider entries: direct-API entries (anthropic,
google, zai, xai) bill on their own rate cards, and OpenRouter's listed
price for the same model id is often different — comparing those would
produce false drift (see the glm-5-2 PRICE NOTE in models.yaml).
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

import yaml

CATALOGUE = Path(__file__).parent / "models.yaml"
MODELS_API = "https://openrouter.ai/api/v1/models"
# Ignore sub-cent-per-M rounding; flag anything that moves a real cost estimate.
TOLERANCE = 0.005


def live_models() -> dict:
    with urllib.request.urlopen(MODELS_API, timeout=30) as r:
        data = json.loads(r.read())["data"]
    return {m["id"]: m for m in data}


def check() -> list[dict]:
    catalogue = yaml.safe_load(CATALOGUE.read_text())["models"]
    live = live_models()
    findings = []
    for m in catalogue:
        if m.get("provider") != "openrouter":
            continue
        or_id = m["openrouter_id"]
        lm = live.get(or_id)
        if lm is None:
            findings.append({"id": m["id"], "openrouter_id": or_id,
                             "kind": "delisted",
                             "detail": "no longer listed on OpenRouter"})
            continue
        live_in = float(lm["pricing"]["prompt"]) * 1e6
        live_out = float(lm["pricing"]["completion"]) * 1e6
        if (abs(live_in - m["input_per_m"]) > TOLERANCE
                or abs(live_out - m["output_per_m"]) > TOLERANCE):
            findings.append({
                "id": m["id"], "openrouter_id": or_id, "kind": "price",
                "catalogued": [m["input_per_m"], m["output_per_m"]],
                "live": [round(live_in, 4), round(live_out, 4)],
            })
        live_ctx = lm.get("context_length")
        if live_ctx and live_ctx != m["context"]:
            findings.append({
                "id": m["id"], "openrouter_id": or_id, "kind": "context",
                "catalogued": m["context"], "live": live_ctx,
            })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        findings = check()
    except Exception as e:
        print(f"price_watch: fetch/parse failed: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(findings, indent=2))
        return 1 if findings else 0
    if not findings:
        print("✓ catalogue matches OpenRouter live pricing")
        return 0
    print(f"✗ {len(findings)} drift(s) between models.yaml and OpenRouter live:")
    for f in findings:
        if f["kind"] == "price":
            c, l = f["catalogued"], f["live"]
            print(f"  {f['id']:20s} price  ${c[0]}/{c[1]} catalogued → "
                  f"${l[0]}/{l[1]} live  ({f['openrouter_id']})")
        elif f["kind"] == "context":
            print(f"  {f['id']:20s} context  {f['catalogued']:,} catalogued → "
                  f"{f['live']:,} live  ({f['openrouter_id']})")
        else:
            print(f"  {f['id']:20s} {f['detail']}  ({f['openrouter_id']})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
