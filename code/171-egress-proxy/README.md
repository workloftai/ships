# 171 · Egress by name, not by IP (egress-guard phase 2)

Default-deny egress for an agent fleet, in two phases.

**Phase 1** (Ship #160): `allowlist.py` (evidence-derived, one reason per host) and
`egress_guard.py` (`audit`, `check`, `gen-nft` for a NOT-ARMED nftables ruleset).

**Phase 2**: `egress_proxy.py`, a hostname-allowlisting forward proxy. It borrows
three ideas from [Forge](https://github.com/initializ/forge) (not the runtime):

1. Allowlist by **name** at a proxy, not by IP at a firewall (CDN IPs drift and are shared).
2. **Layered policy**: `allowlist.py` is the platform bound; `policies/<loop>.json`
   can only narrow it. `lint` refuses any loop policy that widens.
3. **NDJSON audit** with a correlation id (the run id) on every connection.

Plus: it reads the TLS ClientHello and kills the tunnel if the SNI differs from
the CONNECT host, and it refuses to bind anything but loopback.

```bash
python3 egress_proxy.py serve --mode monitor        # log what enforce would block
python3 egress_proxy.py serve --mode enforce        # 403 anything off policy
./egress-run research-digest -- python3 digest.py   # opt one loop in, tagged
python3 egress_proxy.py report                      # per-loop: allowed / blocked
python3 egress_proxy.py lint                        # loop policies only narrow
python3 tests/test_egress_proxy.py                  # 19 end-to-end checks
```

## Honest limits

- **Opt-in.** A process that ignores `HTTPS_PROXY`, or unsets it, goes around the
  proxy. The proxy is the control; the nftables default-deny (allow only the proxy
  out) is what makes it unskippable. Arming that stays a human decision.
- **SNI can be absent** (ECH, or non-TLS). It is logged as `sni: null`, not blocked.
- **Plain HTTP** is forwarded with the Host from the request line; keep-alive
  requests after the first on the same connection are not re-checked.
