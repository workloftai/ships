"""Tiny calculator. Operations live in one registry that many agents edit."""

OPS = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
}


def compute(op, a, b):
    if op not in OPS:
        raise ValueError(f"unknown op: {op}")
    return OPS[op](a, b)
