# Seeded bugs (ground truth)

Each sample carries known defects that a happy-path test passes straight over.
The eval scores a reviewer on how many it catches and how much noise it adds.

## samples/orders.py

1. **Full-table load, filter in Python** (`load_all_orders` + list comprehension).
   Every refund pulls the entire `orders` table into memory and filters client
   side. Fine on two rows, a table scan and OOM risk in production. This is the
   class of defect that passes every test because tests use tiny fixtures.
   Match keywords: `orders`, and one of `entire`/`all`/`table`/`memory`/`scan`.
   Expected severity: HIGH.

2. **Float money maths** (`net = take * 975 / 1000`, stored to `refunded_cents`).
   Currency handled as floating point, writing fractional cents into an integer
   cents field. Silent rounding loss that reconciliation catches months later.
   Match keywords: one of `float`/`cents`/`rounding`/`fractional`.
   Expected severity: HIGH.

## samples/auth.py

3. **Fail-open on missing expiry** (`if expires_at is None: return True`).
   A session with a token but no `expires_at` is treated as valid forever. An
   attacker (or a bug upstream that drops the field) gets a session that never
   expires. The happy-path test never exercises the no-expiry branch.
   Match keywords: one of `expiry`/`expires`/`expire`/`never`/`fail-open`/`forever`.
   Expected severity: HIGH.

## samples/clean.py

No seeded defect. Any HIGH/CRITICAL finding here is a false positive.

---

A reviewer "catches" a bug if it reports a finding whose location and mechanism
match one of the above. The keyword lists make that check reproducible; they are
a heuristic, not a judge, so eyeball the misses.
