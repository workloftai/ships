# 097 — The effort dial

Companion code for [Every agent in the fleet was set to maximum effort](https://workloft.ai/ships/the-effort-dial-2026-07-03.html).

Anthropic's `output_config.effort` parameter (low / medium / high / xhigh / max)
is the biggest cost lever on a Claude bill, and the default is high. If your
router already picks models by a cost-quality tier, the tier should set effort
too — same decision, same place.

`effort_router.py` is the pattern, dependency-free:

- `premium` keeps the API default (nothing sent — keeps request bodies
  byte-stable for prompt caching)
- `balanced` sends `medium`
- `cheap` sends `low`
- a model gate stops the parameter reaching models that 400 on it
  (Haiku 4.5, pre-4.6 Sonnets)

```python
from effort_router import apply_effort

body = {"model": "claude-opus-4-8", "max_tokens": 1024, "messages": [...]}
apply_effort(body, tier="balanced")   # adds output_config.effort = "medium"
```

Run the tests:

```
python3 test_effort_router.py
```

Also worth doing while you're in there: headless Claude Code cron jobs accept
`--effort <level>` — the harness default for coding is xhigh, above even the
API default, so overnight jobs are the first place to look.
