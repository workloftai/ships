# egress_guard — default-deny egress for an agent fleet, the safe way

A default-deny firewall on a live box running agents is one wrong line from
cutting off its own database, message bridge, model APIs and git at once, after
which your alerting cannot even tell you. This does the safe 90% and stops short
of the dangerous 10%: it inventories and prepares, it does not arm.

## Three verbs

```bash
python3 egress_guard.py audit          # static dry-run: every outbound host in the
                                       # code, classified vs the allowlist
python3 egress_guard.py check HOST     # is one host allowed by policy
python3 egress_guard.py gen-nft --out egress.nft   # emit a DEFAULT-DENY nftables
                                       # ruleset, resolved to current IPs, NOT armed
```

- **audit** walks your code for `https?://host` references, and buckets each host
  into ALLOWED / OFF-LIST / DENY-FLAGGED. It never touches the network, so it is
  safe to run anywhere and in CI. It is how you learn what you must permit before
  you permit nothing by default.
- **gen-nft** writes an `nft` ruleset with `policy drop`, allowing loopback,
  established/related, DNS, and the allowlisted hosts resolved to IPs, dropping
  and logging the rest. It prints a file with a NOT-ARMED header. Applying it is a
  human step (`sudo nft -f`), on purpose.

## Make it yours

Edit `allowlist.py`: base domains grouped by purpose, one line of justification
each, plus a small denylist of things you never want reached (URL shorteners,
paste sites) so the audit flags them if they turn up. `egress.nft.example` is a
sample of what `gen-nft` produces (IPs will differ for you).

## The honest limits

- IP allowlisting is a coarse backstop. CDN IPs drift and are shared between
  unrelated sites, so the robust control is an egress **proxy** that allowlists by
  TLS SNI / Host header. The L3 ruleset is the belt; the proxy is the braces.
- This does not enforce anything. Arming default-deny on a live agent box can
  sever the fleet's own lifelines, and an agent should never cut off its own
  ability to call for help unsupervised. Inventory and generate here; a human with
  a console open pulls the trigger.

Part of [Workloft Ships](https://workloft.ai/ships/). Steal what you like.
