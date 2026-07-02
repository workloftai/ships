# Route by token shape

Three small pieces behind the ship "96% of our agent's tokens are cache reads.
That decided our model routing"
(https://workloft.ai/ships/96-percent-of-tokens-are-cache-reads-2026-07-02.html):

- `bench_fable5_vs_opus48.py` — cost-per-correct bench: six hard exact-answer
  reasoning tasks, reference answers brute-forced in the script so grading is
  exact. Compares Opus 4.8 (high effort) vs Fable 5 (medium and high effort)
  and counts silent Opus fallbacks. Point `KEYFILE` at your own Anthropic key.
- `model_fallback_guard.py` — Claude Code UserPromptSubmit hook that catches
  Fable's sticky safety fallback by comparing the transcript's serving model
  with the model configured in settings.json. Fail-open by design.
- `flip_to_three_tier.py` — one-command switch of a Claude Code settings.json
  to the three-tier setup (Opus main loop, Sonnet subagent default), with a
  timestamped backup.

Numbers from our run (2026-07-02, list prices):

| config | correct | output tokens | $ per correct |
|---|---|---|---|
| Opus 4.8, effort high | 6/6 | 7,433 | $0.0313 |
| Fable 5, effort medium | 5/6 | 2,377 | $0.0245 |
| Fable 5, effort high | 6/6 | 3,325 | $0.0283 |

The twice-the-price model was cheaper per correct answer. Route by token
shape: cache-read-heavy loops on the mid tier, output-heavy hard tasks on the
frontier tier, fan-out on cheap workers.
