"""
Control sample: no seeded defect. A reviewer that reports a HIGH finding here is
adding noise. Used to measure the false-positive rate, which is what erodes
trust in a reviewer faster than a missed bug.
"""


def clamp(value, low, high):
    """Clamp value into [low, high]. Raises if the bounds are inverted."""
    if low > high:
        raise ValueError("low must not exceed high")
    return max(low, min(value, high))


def batched(items, size):
    """Yield successive lists of at most `size` items."""
    if size < 1:
        raise ValueError("size must be >= 1")
    for start in range(0, len(items), size):
        yield items[start : start + size]


if __name__ == "__main__":
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(11, 0, 10) == 10
    assert list(batched([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    print("happy-path test passed")
