"""
Tests for the trust boundary: the parts that do not call a model.

The reviewer's output is untrusted, so the code that turns it into findings has
to be the reliable bit. These test the parse-and-validate path: malformed
findings are dropped, not passed through.

    python3 test_codex_review.py     # no deps, no network
"""

import codex_review as cr


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    assert cond, name


def test_extract_json_bare():
    obj = cr.extract_json('{"findings": []}')
    check("bare json parses", obj == {"findings": []})


def test_extract_json_with_prose():
    raw = 'Here you go:\n{"findings": [{"a": 1}]}\nhope that helps'
    obj = cr.extract_json(raw)
    check("json extracted from surrounding prose", obj == {"findings": [{"a": 1}]})


def test_extract_json_garbage():
    check("unparseable returns None", cr.extract_json("not json at all") is None)


def test_valid_finding_survives():
    f = cr.validate_finding({
        "severity": "HIGH", "file": "a.py", "line": "10",
        "title": "bug", "why": "because", "confidence": 0.9,
    })
    check("valid finding kept", f is not None and f["severity"] == "HIGH")


def test_bad_severity_dropped():
    f = cr.validate_finding({
        "severity": "SPICY", "title": "x", "why": "y", "confidence": 0.5,
    })
    check("unknown severity dropped", f is None)


def test_out_of_range_confidence_dropped():
    f = cr.validate_finding({
        "severity": "LOW", "title": "x", "why": "y", "confidence": 4.0,
    })
    check("confidence > 1 dropped", f is None)


def test_non_numeric_confidence_dropped():
    f = cr.validate_finding({
        "severity": "LOW", "title": "x", "why": "y", "confidence": "high",
    })
    check("non-numeric confidence dropped", f is None)


def test_empty_title_dropped():
    f = cr.validate_finding({
        "severity": "CRITICAL", "title": "  ", "why": "y", "confidence": 0.9,
    })
    check("blank title dropped", f is None)


def test_severity_ordering():
    check("CRITICAL outranks LOW",
          cr.SEVERITY_RANK["CRITICAL"] > cr.SEVERITY_RANK["LOW"])


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)} tests passed")
