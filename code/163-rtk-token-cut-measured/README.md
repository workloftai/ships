# rtk-token-cut-measured

[rtk](https://github.com/rtk-ai/rtk) is a Rust proxy that filters command output
before an agent reads it, advertised at **up to 90%** fewer tokens. This is that
claim, measured on a real repo across a normal orient-search-read agent loop.

## The finding

The aggregate cut was **about a quarter, not 90%**: 25.9% by our own token
estimate, 23.1% by rtk's own ledger. The 90% is real, it is just the
directory-listing case, not the average turn.

```
command               native tok    rtk tok    cut
git status                   760        701     7.8%
git diff                    3434       3365     2.0%
git log -50                 1572       1306    16.9%
grep export src             3657       3595     1.7%
find *.tsx                   272        198    27.2%
ls node_modules             5003        202    96.0%
read 655-line file          7014       7014     0.0%
tree src                     460         45    90.2%
--------------------------------------------------
TOTAL                      22172      16426    25.9%
```

rtk saves most where the output is **noise the agent did not ask for**: a
`node_modules` listing (96%), a file tree (90%), a deduplicated log (17%). It
saves **almost nothing where the output is the payload**: reading a specific file
(0%), a real diff (2%), a targeted grep (2%). The percentage is not a property of
the tool. It is a property of your command mix, and the only way to know yours is
to measure it.

## Why this matters

"Up to 90%" is a benchmark on the friendliest possible command. Your bill is the
weighted average across the commands you actually run. And a quarter of the
command output is not a quarter of your bill: the system prompt, the prior turns
and the model's own output all dilute it, so the share of your metered spend is
smaller again. A quarter off command output for a 10MB binary and one hook is
still a good trade. Just size the trade with your own number.

This is the third in a token-cost line, after the
[router that saved 67%](https://workloft.ai/ships/router-saved-67-all-local-saved-100-2026-08-31.html)
and the [cheap frontier model that cost the most](https://workloft.ai/ships/cheap-frontier-model-cost-the-most-2026-09-04.html).
Same finding each time: measure it on your workload before you believe the headline.

## Run it

```bash
# install rtk (see https://github.com/rtk-ai/rtk) — brew, cargo, or a prebuilt binary
export RTK=$(command -v rtk)          # or an absolute path to the binary
export REPO=/path/to/your/repo
python3 harness.py                    # prints the table above + writes result.json
```

Edit the `CASES` list in `harness.py` to match the commands *your* agent actually
runs. The number you get is yours, not ours.

## Method, stated plainly

- For each command an agent runs to orient/search/read, we capture the full
  combined stdout+stderr it would have to ingest, bare and through rtk.
- We count raw bytes and estimate tokens with the standard rough proxy of
  `chars / 4`. This is an estimate, not a metered invoice.
- rtk's own `rtk gain` ledger is reported as an independent cross-check; on this
  run it said 23.1% against our 25.9%.
- We measured the proxy directly, not a live multi-turn session through the Claude
  Code hook, so this is the *ceiling* of what rtk removes, not a lived A/B.

## Files

- `harness.py` — the A/B measurement.
- `result.json` — the numbers behind the table.
- `example_run.txt` — a captured run against a Next.js repo.

MIT, same as the rest of this repo. rtk itself is Apache-2.0 and not vendored here.
