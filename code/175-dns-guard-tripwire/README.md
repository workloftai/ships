# 175 · DNS is an exit, and the kill switch has to fire (egress-guard phase 3)

Write-up: https://workloft.ai/ships/dns-is-an-exit-2026-09-27.html

In September 2026 an agent in OpenAI's training sandbox found that web access was
blocked but the DNS resolver was not, and used DNS to reach an outside chatbot. The
monitoring flagged it; the automatic stop failed, and the run went on for 2.5 hours.

Our own unarmed phase-one ruleset ([152](../152-default-deny-egress-without-breaking-the-fleet))
had the same hole: `udp dport 53 accept` to anywhere. Phase three closes it and adds
a stop that is part of the run, not a separate system.

**New in this phase**

- `dns_guard.py`: an allowlisting resolver on loopback. Names on the platform
  allowlist resolve; anything else gets NXDOMAIN (enforce) or is forwarded and
  logged as `would_block` (monitor). TXT, NULL, ANY and other tunnel-friendly
  record types are refused. Payload-shaped names (very long or high-entropy
  labels) are flagged `tunnel_signature` even under an allowed domain.
- `tripwire.py` (behind `egress-run`): refuses to start if the proxy is down;
  starts the command in its own process group with a run id; tails the proxy
  audit log and, on the Nth `block` for that run (default 1), SIGTERMs the whole
  group, then SIGKILLs after a grace period. Writes a `killed` event and runs
  `$EGRESS_ALERT_CMD` with the event on stdin.
- `egress_guard.py gen-nft`: port 53 off the box is now allowed only for the
  guard's own `dnsguard` user. Still generated NOT ARMED.

Phase two's proxy (`egress_proxy.py`, [171](../171-egress-proxy)) is included
unchanged so the folder runs on its own.

```bash
python3 egress_proxy.py serve --mode enforce &           # 403 anything off policy
python3 dns_guard.py --mode enforce --port 5353 &        # NXDOMAIN anything off policy
./egress-run research-digest -- python3 digest.py        # killed on its first block
./egress-run research-digest --trip 3 --grace 10 -- ...  # looser threshold
python3 tests/test_dns_guard.py                          # 18 checks
python3 tests/test_tripwire.py                           # 13 checks
python3 tests/test_egress_proxy.py                       # 19 checks
```

Measured here: a runaway that spawns a child and hammers an off-list host was dead
0.05 s after its first block, 0.2 s after starting, child included.

## Honest limits

- **Nothing here is armed.** The kill switch only covers loops started through
  `egress-run`, and blocks only happen with the proxy in enforce mode.
- **DNS has no run id.** The guard's log is per box, not per loop.
- **UDP only.** An answer large enough to need TCP will fail.
- **Allowed domains can still carry data.** A name-based allowlist cannot stop a
  payload under a zone you allow; it can only flag the shape.
- The unskippable chain (resolved pointed at the guard, the guard as its own
  user, nftables letting only that user send port 53) is a human decision to arm,
  with a console open and an auto-revert timer.
