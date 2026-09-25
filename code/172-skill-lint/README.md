# 172 · skill-lint: find where your agent's instructions disagree

An agent with thirty skill files, slash-commands and SOPs has thirty chances to
be told two different things. It will not complain. It picks one, quietly, and
you find out from the output. `skill_lint.py` finds those contradictions before
the agent does.

Inspired by [SkillSpec](https://arxiv.org/abs/2609.06052) (arXiv 2609.06052),
which treats skill correctness as specification reasoning and finds that the
checker's context has to be rationed: too much and it inherits the author's
assumptions, too little and it invents problems. So this runs in masked views.

| pass | view | what it does |
|---|---|---|
| 1 reality | none (no model) | every path and CLI a skill names: does it exist on this box? |
| 2 extract | one document at a time | pull each normative rule with a verbatim quote |
| 3 conflict | rules only, no documents | propose rule pairs from different docs that cannot both be obeyed |
| 4 verify | the two source documents | rule REAL, SCOPED (different situations) or SUPERSEDED (explicitly dated/retired) |

Every quote at every stage is checked verbatim against the file. A quote that is
not in the file is dropped as a hallucination. Model calls are cached on disk by
content hash, so a rerun on an unchanged corpus is free.

```bash
python3 skill_lint.py reality                      # no API key needed
ANTHROPIC_API_KEY=... python3 skill_lint.py full --out report.json
```

Edit `CORPUS_GLOBS` at the top to point at your own skills. Exit code 1 if
anything is found, so it can sit in CI or a nightly job.

## First run on our own fleet

30 documents, 18,857 words. 47 paths and CLIs checked, none missing. 661 rules
extracted (2 dropped for quotes that were not in the source). 54 candidate
conflicts, of which the verifier ruled 34 SCOPED, 12 SUPERSEDED, 1 bad quote,
7 REAL, and 1 of those a duplicate: **6 real contradictions**. We read all six
by hand; all six hold up, one is a judgement call.

## Limits

- It compares documents with each other, not with practice. A skill that
  describes a folder layout you stopped using months ago is invisible to it
  unless the path is concrete enough for pass 1 to check.
- Recall is unmeasured. The verifier is told to be sceptical, so it will miss
  some real clashes rather than cry wolf.
- It flags; it does not fix. Which rule wins is a human decision.
