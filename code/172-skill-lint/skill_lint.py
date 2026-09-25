#!/usr/bin/env python3
"""
skill_lint: find the places where an agent's instructions disagree with each
other, or with the machine they run on.

Inspired by SkillSpec (arXiv 2609.06052), which treats skill correctness as
specification reasoning: derive what each skill SAYS it should do, infer what it
actually encodes, and flag the gaps. Their key finding is about context: give
the checker too much and it inherits the author's assumptions, give it too
little and it invents problems. So this works in masked views, cheapest first.

  1. reality   (deterministic, no model)  Every file path and CLI a skill tells
               the agent to use: does it exist on this box? A skill that points
               at a file that is not there fails silently, because the model
               improvises around it.
  2. extract   (local view, one doc at a time)  Pull each normative rule (must,
               never, always, HARD, only, default) with a verbatim quote. The
               model sees one document, so it cannot "harmonise" it with others.
  3. conflict  (masked holistic view)  The model sees ONLY the extracted rules,
               never the documents, and proposes pairs that cannot both be
               obeyed.
  4. verify    (neighbourhood view)  Each candidate pair goes back to the model
               with the full text of just the two documents involved, and it
               must rule: REAL conflict, SCOPED (both true in different
               situations), or SUPERSEDED (one is explicitly dated/marked as
               replacing the other). Only REAL survives.

Every quote at every stage is checked verbatim against the source file. A
finding whose quote is not in the file is dropped as a hallucination.

Usage:
  python3 skill_lint.py reality
  python3 skill_lint.py full [--out report.json]
"""

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

HOME = os.path.expanduser("~")
CORPUS_GLOBS = [
    f"{HOME}/.claude/commands/*.md",
    f"{HOME}/.claude/skills/*/SKILL.md",
    f"{HOME}/.claude/skills/*.md",
    f"{HOME}/.claude/projects/*/memory/SOP_ROUTING.md",
    f"{HOME}/STYLE.md",
    f"{HOME}/CLAUDE.md",
]
MODEL = "claude-opus-5"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")


def corpus():
    docs = {}
    for g in CORPUS_GLOBS:
        for p in sorted(glob.glob(g)):
            docs[p.replace(HOME, "~")] = open(p, errors="ignore").read()
    return docs


def norm(s):
    return re.sub(r"\s+", " ", s.replace("**", "").replace("`", "")).strip().lower()


def quote_ok(quote, text):
    q = norm(quote)
    return len(q) >= 12 and q in norm(text)


def line_of(quote, text):
    q = norm(quote)[:40]
    for i, ln in enumerate(text.splitlines(), 1):
        if q[:25] in norm(ln):
            return i
    return None


# ---------------------------------------------------------------- 1 reality

PATH_RE = re.compile(r"(?<![\w/.])((?:~|/home/workloft)/[\w./@+-]+)")
PLACEHOLDER = re.compile(r"<|>|\{|\}|\*|NNN|YYYY|MM-DD|\.\.\.|…|\$")
FENCE_RE = re.compile(r"```(?:bash|sh|shell)?\n(.*?)```", re.S)
SHELL_BUILTINS = {"cd", "echo", "export", "if", "then", "fi", "for", "do", "done",
                  "cat", "grep", "curl", "git", "python3", "python", "ls", "sed",
                  "set", "source", "exit", "true", "false", "test", "[", "mkdir",
                  "cp", "mv", "rm", "head", "tail", "jq", "npm", "npx", "node",
                  "date", "sleep", "cut", "wc", "sort", "find", "tee", "xargs",
                  "chmod", "touch", "printf", "read", "while", "case", "esac",
                  "else", "elif", "function", "return", "local", "bash", "sh"}


def reality(docs):
    findings, checked = [], 0
    for doc, text in docs.items():
        seen = set()
        created = set(re.findall(r"mkdir -p (\S+)", text))  # made on demand, not missing
        for i, ln in enumerate(text.splitlines(), 1):
            for mo in PATH_RE.finditer(ln):
                path = mo.group(1).rstrip(".,:;)'\"`")
                nxt = ln[mo.end():mo.end() + 1]
                if (path in seen or PLACEHOLDER.search(path) or nxt in "*<{$"
                        and nxt or any(path.startswith(c) for c in created)):
                    continue
                seen.add(path)
                checked += 1
                if not os.path.exists(os.path.expanduser(path.replace("/home/workloft", HOME))):
                    findings.append({"kind": "missing_path", "doc": doc, "line": i,
                                     "what": path, "evidence": ln.strip()[:200]})
        for block in FENCE_RE.findall(text):
            for ln in block.splitlines():
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                tok = re.split(r"[\s|;&()]", ln, 1)[0]
                if (not tok or "=" in tok or tok.startswith(("-", "$", "\"", "'", "/", "~", ".", "<"))
                        or tok in SHELL_BUILTINS or tok in seen or not re.match(r"^[a-z][\w-]*$", tok)):
                    continue
                seen.add(tok)
                checked += 1
                if shutil.which(tok) is None:
                    findings.append({"kind": "missing_cli", "doc": doc,
                                     "line": line_of(ln, text), "what": tok,
                                     "evidence": ln[:200]})
    return findings, checked


# ---------------------------------------------------------------- model I/O

def _client():
    import anthropic
    return anthropic.Anthropic()


def ask(system, user, schema, tag):
    """One structured call, cached on disk by content hash so reruns are free."""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha256(json.dumps([MODEL, system, user, schema]).encode()).hexdigest()[:24]
    path = os.path.join(CACHE, f"{tag}-{key}.json")
    if os.path.exists(path):
        return json.load(open(path))
    import anthropic
    with _client().messages.stream(
        model=MODEL, max_tokens=32000, system=system,
        thinking={"type": "adaptive"},
        output_config={"effort": "high",
                       "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"{tag}: refused")
    text = next(b.text for b in msg.content if b.type == "text")
    out = json.loads(text)
    json.dump(out, open(path, "w"))
    return out


# ---------------------------------------------------------------- 2 extract

RULES_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["rules"],
    "properties": {"rules": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["topic", "rule", "quote"],
        "properties": {
            "topic": {"type": "string"},
            "rule": {"type": "string"},
            "quote": {"type": "string"},
        }}}},
}

EXTRACT_SYS = (
    "You extract the normative rules from ONE instruction document written for an AI "
    "agent. A rule is anything the agent must, must never, should always, or by default "
    "does: formats, paths, channels, limits, ordering, which tool to use. Skip pure "
    "description. For each rule give: topic (2-5 lowercase words naming what it governs, "
    "e.g. 'social post links', 'github mirror path', 'hero image style'), rule (one "
    "plain sentence), and quote (an EXACT verbatim span copied from the document, 12-200 "
    "characters, that states the rule). Do not paraphrase the quote. Do not judge the "
    "rules or compare them with anything outside this document."
)


def extract(docs):
    def one(item):
        doc, text = item
        out = ask(EXTRACT_SYS, f"Document: {doc}\n\n{text}", RULES_SCHEMA, "extract")
        rules = []
        for r in out["rules"]:
            if quote_ok(r["quote"], text):
                r["doc"] = doc
                r["line"] = line_of(r["quote"], text)
                rules.append(r)
        return rules, len(out["rules"])
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, docs.items()))
    rules = [r for rs, _ in res for r in rs]
    proposed = sum(n for _, n in res)
    for i, r in enumerate(rules):
        r["id"] = f"R{i}"
    return rules, proposed


# ---------------------------------------------------------------- 3 conflict

CONFLICT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["conflicts"],
    "properties": {"conflicts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["a", "b", "why"],
        "properties": {"a": {"type": "string"}, "b": {"type": "string"},
                       "why": {"type": "string"}}}}},
}

CONFLICT_SYS = (
    "You are given rules extracted from an AI agent's instruction documents (skills, "
    "slash-commands, SOPs, style guides). Each has an id, source doc, topic and text. "
    "Find PAIRS of rules from DIFFERENT documents that an agent could not obey at the "
    "same time in the same situation: they prescribe different values, paths, channels, "
    "orders or limits for the same thing. Do not flag rules that merely overlap, "
    "restate, or add detail. Return the ids of each pair and one sentence saying what "
    "the agent would be forced to choose between. Prefer precision over recall."
)


def conflicts(rules):
    listing = "\n".join(f'{r["id"]} [{r["doc"]}] ({r["topic"]}) {r["rule"]}' for r in rules)
    out = ask(CONFLICT_SYS, listing, CONFLICT_SCHEMA, "conflict")
    byid = {r["id"]: r for r in rules}
    seen, cands = set(), []
    for c in out["conflicts"]:
        a, b = byid.get(c["a"]), byid.get(c["b"])
        if not a or not b or a["doc"] == b["doc"]:
            continue
        k = tuple(sorted([a["id"], b["id"]]))
        if k in seen:
            continue
        seen.add(k)
        cands.append({"a": a, "b": b, "why": c["why"]})
    return cands


# ---------------------------------------------------------------- 4 verify

VERIFY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["verdict", "reason", "quote_a", "quote_b"],
    "properties": {
        "verdict": {"type": "string", "enum": ["REAL", "SCOPED", "SUPERSEDED"]},
        "reason": {"type": "string"},
        "quote_a": {"type": "string"},
        "quote_b": {"type": "string"},
    },
}

VERIFY_SYS = (
    "Two instruction documents for the same AI agent may contradict each other. You get "
    "the full text of both and the suspected conflict. Rule:\n"
    "REAL: in some realistic situation the agent must break one to obey the other, and "
    "nothing in either document says which wins.\n"
    "SCOPED: both hold because they apply to different situations, channels or content "
    "types, as the text makes clear.\n"
    "SUPERSEDED: one document explicitly marks its rule as replacing, deprecating or "
    "overriding the other (e.g. a dated lock, 'supersedes', 'retired').\n"
    "Give a one-sentence reason and an exact verbatim quote from each document (12-200 "
    "characters) that shows the clash. Be sceptical: most suspected conflicts are SCOPED."
)


def verify(cands, docs):
    def one(c):
        a, b = c["a"], c["b"]
        user = (f"Suspected conflict: {c['why']}\n\nRule A ({a['doc']}): {a['rule']}\n"
                f"Rule B ({b['doc']}): {b['rule']}\n\n=== DOCUMENT A: {a['doc']} ===\n"
                f"{docs[a['doc']]}\n\n=== DOCUMENT B: {b['doc']} ===\n{docs[b['doc']]}")
        v = ask(VERIFY_SYS, user, VERIFY_SCHEMA, "verify")
        v["quotes_verified"] = (quote_ok(v["quote_a"], docs[a["doc"]])
                                and quote_ok(v["quote_b"], docs[b["doc"]]))
        return {**c, "verify": v}
    with ThreadPoolExecutor(6) as ex:
        return list(ex.map(one, cands))


# ---------------------------------------------------------------- report

def main():
    ap = argparse.ArgumentParser(prog="skill_lint")
    ap.add_argument("mode", choices=["reality", "full"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    docs = corpus()
    words = sum(len(t.split()) for t in docs.values())
    print(f"corpus: {len(docs)} documents, {words} words\n")

    real, checked = reality(docs)
    print(f"[1 reality] {checked} paths/CLIs checked, {len(real)} do not exist on this box")
    for f in real:
        print(f"  {f['kind']:12} {f['doc']}:{f['line']}  {f['what']}")
    report = {"corpus": list(docs), "words": words, "reality": real}

    if a.mode == "full":
        rules, proposed = extract(docs)
        print(f"\n[2 extract] {len(rules)} rules kept, {proposed - len(rules)} dropped "
              f"(quote not found verbatim in the source)")
        cands = conflicts(rules)
        print(f"[3 conflict] {len(cands)} candidate conflicts from the masked rule view")
        checked = verify(cands, docs)
        keep, dupes = [], 0
        for c in checked:
            if c["verify"]["verdict"] != "REAL" or not c["verify"]["quotes_verified"]:
                continue
            sig = (c["a"]["doc"], c["b"]["doc"], norm(c["verify"]["quote_a"]))
            if any(sig == (k["a"]["doc"], k["b"]["doc"], norm(k["verify"]["quote_a"])) for k in keep):
                dupes += 1  # same clash reached from a second rule pair
                continue
            keep.append(c)
        tally = {}
        for c in checked:
            k = c["verify"]["verdict"] + ("" if c["verify"]["quotes_verified"] else "/bad-quote")
            tally[k] = tally.get(k, 0) + 1
        print(f"[4 verify] {tally} -> {len(keep)} REAL ({dupes} duplicate merged)\n")
        for i, c in enumerate(keep, 1):
            v = c["verify"]
            print(f"CONFLICT {i}: {c['a']['topic']}")
            print(f"  {c['a']['doc']}:{c['a']['line']}  \"{v['quote_a']}\"")
            print(f"  {c['b']['doc']}:{c['b']['line']}  \"{v['quote_b']}\"")
            print(f"  -> {v['reason']}\n")
        report.update(rules=len(rules), rules_dropped=proposed - len(rules),
                      candidates=len(cands), verify_tally=tally,
                      conflicts=[{"a_doc": c["a"]["doc"], "a_line": c["a"]["line"],
                                  "b_doc": c["b"]["doc"], "b_line": c["b"]["line"],
                                  "topic": c["a"]["topic"], **c["verify"]} for c in keep],
                      rejected=[{"a_doc": c["a"]["doc"], "b_doc": c["b"]["doc"],
                                 "why": c["why"], **c["verify"]} for c in checked if c not in keep])
    if a.out:
        json.dump(report, open(a.out, "w"), indent=1)
        print(f"report -> {a.out}")
    return 1 if report["reality"] or report.get("conflicts") else 0


if __name__ == "__main__":
    sys.exit(main())
