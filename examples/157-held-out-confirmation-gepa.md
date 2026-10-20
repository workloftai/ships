# Our prompt optimiser was promoting luck

**Date:** 2026-10-20
**Author:** Alfred + Bob
**Category:** fix

Our nightly prompt optimiser (GEPA) staged 35 "winning" prompts for review since June, each claiming 5 to 22.5 points over the live prompt. Re-run today, all six of the most recent winners score below the prompt they beat. The same prompt, run three times on the same 40 test items, scored 97.5, 95.0 and 90.0, and the bar to win was 3 points. We added a held-out confirmation step.

Live article: https://workloft.ai/ships/held-out-confirmation-gepa-2026-10-20.html

## What we did

- Re-ran the live prompt three times to measure run-to-run noise: a 7.5 point spread on 40 items.
- Replayed the six most recent staged winners three times each. All six average below the live prompt's 94.2. The like-for-like case (staged 18 October, claimed +5) averages 90.8. The other five were staged against an older model route, so treat them as weaker evidence.
- Split the 40 items into 28 selection rows and 12 confirmation rows. Variants are ranked on selection only. A would-be winner must also beat the live prompt on the 12 rows it was never chosen on, or it is not staged. No extra API cost: every row is still scored once.
- First run with the split: two variants tied for first on selection. On the unseen rows one gained 8 points, the other lost 8.
- Retired a second, baseline-only optimiser that had produced nothing since May.

The idea comes from EvoHeir (arXiv 2610.22029): choosing a winner and measuring its win on the same questions makes the win look bigger than it is.

### Steal this: the split

Deterministic (a row never changes side between runs) and stratified by the gold label, so both halves keep the same answer mix.

```python
def _split_rows(eval_set: list[dict], holdout_pct: float) -> tuple[list[int], list[int]]:
    """Deterministic split keyed on row content, so a row never changes side
    between runs and the confirm rows are never used for selection. Stratified
    by gold verdict so both halves keep the eval set's label mix."""
    n = len(eval_set)
    if holdout_pct <= 0 or n < MIN_ROWS_FOR_HOLDOUT:
        return list(range(n)), []
    def _key(i):
        return hashlib.sha256(json.dumps(eval_set[i], sort_keys=True).encode()).hexdigest()
    groups: dict = {}
    for i, r in enumerate(eval_set):
        gold = r.get("opus_label") or r.get("flash_label") or {}
        label = gold.get("verdict") if isinstance(gold, dict) else None
        groups.setdefault(label, []).append(i)
    hold: list[int] = []
    for idx in groups.values():
        idx.sort(key=_key)
        hold += idx[:round(len(idx) * holdout_pct)]
    if len(hold) < MIN_CONFIRM_ROWS:
        rest = sorted((i for i in range(n) if i not in hold), key=_key)
        hold += rest[:MIN_CONFIRM_ROWS - len(hold)]
    hold_set = set(hold)
    return [i for i in range(n) if i not in hold_set], sorted(hold_set)
```

Then: rank variants on `selection` rows, and only stage the top one if it also beats the baseline on `holdout` rows.

## Why it was worth doing

An optimiser that only ever looks at one score on one small set will find noise and call it progress. A human approval gate does not fix that. It just means someone reviews a list of coin flips.

## What's still off

Twelve confirmation rows is small: one item is worth 8 points, so the step catches flukes but does not make a win trustworthy. The real fix is a larger test set and a winning bar set above the measured noise. Until then we promote nothing the optimiser stages.
