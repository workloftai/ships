# cite-check

Confirm every citation in a draft is real before it ships.

`cite-check` reads a draft (a Note, a post, an email, anything), pulls out every
URL and arXiv ID, and fetches each one to confirm it actually exists. A draft
that cites a dead link or a fabricated arXiv ID fails the gate, so it never
reaches publish.

This is **bite 1**: the *resolve* check. It answers "is this source real?"
It does not yet answer "does this source support the claim next to it?" — that
is the harder, separate problem (phase 2, a local faithfulness model).

## Why

Agents fabricate citations. They produce a plausible-looking link or an
arXiv ID that does not exist, drop it into otherwise good copy, and nobody
checks. We had a rule about it ("verify every URL", "never fabricate
identifiers") but no automated enforcement. A rule a human has to remember is
not a guard. This is the guard.

## Usage

```
cite-check draft.md            # check a file
cat draft.md | cite-check       # check stdin
cite-check draft.md --json      # machine-readable report
cite-check draft.md --quiet     # only print failures
cite-check draft.md --strict    # also fail if there are NO citations
```

Exit code is `0` when every citation resolves and `1` when any fail, so it
drops straight into a publish pipeline as a blocking gate:

```
cite-check "$DRAFT" || { echo "unverified citation, refusing to publish"; exit 1; }
```

## What it checks

- **URLs** — HEAD request, falling back to a streamed GET when the server
  refuses HEAD (many do). Status under 400 is a pass. Redirects are followed.
- **arXiv IDs** — looked up against the official arXiv API, not a plain page
  fetch, because `arxiv.org/abs/<id>` can return 200 for a non-existent paper.
  A fabricated ID returns a feed with no matching entry, which fails.

## What it does not do (yet)

- Check that the source *supports* the claim (phase 2: local faithfulness model).
- Distinguish a real-but-paywalled page from a real-and-readable one beyond a
  coarse status check.

## Tests

```
python3 test_cite_check.py                 # offline tests only
CITE_CHECK_NET=1 python3 test_cite_check.py # include live network checks
```

Built by Workloft. MIT licensed.
