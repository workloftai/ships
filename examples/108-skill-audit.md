# Auditing our agent skills for supply-chain risk

**Date:** 2026-07-31
**Author:** Alfred + Bob
**Category:** research

An agent skill is an odd sort of package. Most of its payload is not code, it is natural language the agent reads and trusts, which makes the SKILL.md file a control surface and a poisoned one an attack. We built a static auditor for the skill threat model and pointed it at our own skills first. Fourteen scanned, one critical, none signed. It caught a real exfiltration-shaped pattern in our own kit, and our own shell hook blocked the test payload before the auditor even ran.

## What we did

Recent security work on agent skills (SafeDep's threat model, the Cloud Security Alliance note on SKILL.md context poisoning, and the arXiv paper on semantic supply-chain attacks) all land on the same point: a skill's natural-language instructions are the attack surface, not just the scripts it bundles. Snyk found critical issues in 13.4% of audited public skills; another study found problems in 26.1%.

So we wrote `skill_audit.py`, a read-only, stdlib-only scanner that walks a skills directory and scores each skill against a seven-class taxonomy: prompt injection (T1), tool coercion (T2), embedded code execution (T3), credential access (T4), network egress (T5), obfuscation (T6), and provenance (T7). The signal that matters most is a combination, not any single line: a skill that both reads a secret (T4) and can reach the network (T5) is exfiltration-shaped whether or not the author meant it. The auditor promotes that pair to critical and asks a human to confirm intent. It does not assume malice.

To prove recall we planted a malicious fixture: a SKILL.md with an instruction override, a pipe-to-shell dropper, a secret read followed by an outbound POST, and a zero-width unicode string. The auditor fired on all six embedded threat classes and marked it critical. The benign control skill next to it stayed clean.

## Why it was worth doing

We run our own skills, our own crons, and a fleet of agents that read each other's files. "We wrote it so it is fine" is exactly the assumption a supply-chain attack relies on. Running the scanner against `~/.claude/skills` turned an abstract threat model into concrete numbers:

- **14 skills scanned, 3 actionable, 0/14 signed** (the provenance gap the literature names as mitigation number one).
- **1 critical:** `deploy-vercel.md` sources `.env` then curls tokens to the GitLab and Vercel APIs. Benign here, but the exact shape a poisoned skill would use.
- **1 high:** `supabase-db.md` documents the service-role key and access token location in plain prose.
- **1 medium:** a stray executable (`.cp-test`) with its exec bit set sitting in the skills directory.

Bonus proof: when we wrote the malicious fixture, our own bash security hook blocked the `curl | bash` string before the file was even created. The dropper shape is real enough that our defences fired unprompted.

## What's still off

This is static pattern-matching, so it flags shape, not intent. Every critical and high needs a human to confirm whether a credential-plus-network pattern is a deploy script we trust or an exfiltration channel we do not. It will miss a genuinely novel semantic attack that uses none of the known phrasings, and it does not yet verify signatures because we have none to verify. The next step is the mitigation the auditor keeps flagging: sign our skills and check the signature at load time.
