from calc import compute

def test_all_ops_present():
    # Every agent's op must survive the merge, or this fails.
    assert compute("add", 6, 2) == 8
    assert compute("sub", 6, 2) == 4
    assert compute("mul", 6, 2) == 12   # agent 1
    assert compute("div", 6, 2) == 3    # agent 2
    assert compute("pow", 6, 2) == 36   # agent 3

if __name__ == "__main__":
    test_all_ops_present()
    print("PASS: all 5 ops present")
