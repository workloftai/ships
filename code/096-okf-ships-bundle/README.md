# okf-ships

The Workloft Ships library as an Open Knowledge Format (OKF v0.1) bundle,
plus the converter and the spot-check that produced our verdict on the
standard.

OKF is Google Cloud's June 2026 spec for LLM-wiki-style knowledge bases:
a directory of markdown files with YAML frontmatter, one required field
(`type`), optional per-directory `index.md` files for progressive
disclosure. Spec: github.com/GoogleCloudPlatform/knowledge-catalog
(okf/SPEC.md, Apache 2.0).

## Contents

- `build_bundle.py` — converts the machine-readable markdown siblings of
  workloft.ai/ships into a conformant bundle: one concept per ship,
  `type: Ship`, title/description/resource/tags/timestamp frontmatter,
  month-grouped hierarchy, generated index.md at every level, root
  `okf_version` declaration.
- `check_conformance.py` — validates a tree against SPEC §9 (frontmatter
  parseable, `type` non-empty, index.md files well-formed). The bundle
  passes: 95 concepts, 0 violations.
- `eval.py` — the spot check. Three known-answer questions asked over
  (a) the raw ships directory and (b) the OKF bundle, each in a fresh
  headless Claude session told to answer only from local files. Records
  correctness, files read and wall-clock time. n=3, one run per
  condition: a spot check, not a benchmark.
- `bundle/` — the output. 95 ships, ~415 KB of markdown. Take it: point
  your agent at this directory (or give it the OKF spec first) and ask
  questions about two months of Workloft builds.
- `eval-results.json` — raw results from the run reported in the ship
  article.

## Reproduce

```bash
python3 build_bundle.py            # rebuild bundle/ from the live site siblings
python3 check_conformance.py bundle
python3 eval.py                    # 6 headless Claude sessions, ~5-10 min
```
