# Model prices are config that rots

Companion code for the Workloft ship: [Model prices are config that rots](https://workloft.ai/ships/model-prices-are-config-that-rots-2026-07-03.html).

In June 2026, on one gateway: DeepSeek V4-flash fell 36% (and its context window
quadrupled), Kimi K2.7-code rose 21%, and a frontier model left and re-entered
the catalogue inside 18 days. If your router's price table is a hand-maintained
file, every one of those events silently wrongs your cost estimates until a
human happens to re-check.

`price_watch.py` treats the price table like a dependency lockfile: diff it
against the provider's live catalogue, exit non-zero on drift, say exactly what
moved. Run it in cron and page yourself only when something changed.

## Usage

```
python3 price_watch.py            # human report
python3 price_watch.py --json     # machine-readable
```

Exit codes: `0` catalogue matches live, `1` drift found, `2` fetch failed.

It expects a `models.yaml` next to it with entries shaped like:

```yaml
models:
  - id: deepseek-v4-flash
    provider: openrouter
    openrouter_id: deepseek/deepseek-v4-flash
    input_per_m: 0.09      # USD per 1M input tokens
    output_per_m: 0.18     # USD per 1M output tokens
    context: 1048576
```

Only `provider: openrouter` entries are checked, on purpose: direct-API
entries bill their own rate cards, and the gateway's listed price for the same
model id is often different. Comparing those would report false drift.

Adapt the fetch to any provider with a models endpoint; the pattern is the
point, not the URL.

## Requires

Python 3.9+, `pyyaml`. No other dependencies.
