#!/usr/bin/env python3
"""
Generate golden_set_v2.json — the FRONTIER-tier eval set.
Every golden answer is COMPUTED here by a reference implementation, so the
answer key is provably correct (no hand-authored answers to get wrong).

Covers the auto-gradable slice of Astra's spike band:
  - hard quantitative / number-theory reasoning (exact integer answers)
  - harder algorithmic coding (tricky DP / edge cases)
  - larger-context multi-hop retrieval + reasoning

NOT covered (needs a live tool/browser harness, not a text API) and flagged
as v3: long-horizon browser/computer-use, and cyber/vuln exploitation.
Also: true >512K context is skipped because Opus's window is smaller, so a
head-to-head there would be unfair; we use a large-but-fair ~fits-both context.
"""
import json, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
tasks = []

# ---------- MATHS (computed answers) ----------

# m1: largest prime factor of a big semiprime-ish number (Project Euler #3 style)
def largest_prime_factor(n):
    f = 2; last = None
    while f * f <= n:
        while n % f == 0:
            last = f; n //= f
        f += 1
    return n if n > 1 else last
N1 = 600851475143
tasks.append({
    "id": "v2-math-01", "category": "math_hard",
    "prompt": f"What is the largest prime factor of {N1}? Reason it through, then end with a line formatted exactly: ANSWER: N",
    "grader": {"type": "numeric", "expected": largest_prime_factor(N1), "tol": 0.5},
})

# m2: number of trailing zeros in K!
def trailing_zeros_factorial(k):
    c = 0; p = 5
    while p <= k:
        c += k // p; p *= 5
    return c
K2 = 2026
tasks.append({
    "id": "v2-math-02", "category": "math_hard",
    "prompt": f"How many trailing zeros are there in {K2}! (the factorial of {K2})? End with a line formatted exactly: ANSWER: N",
    "grader": {"type": "numeric", "expected": trailing_zeros_factorial(K2), "tol": 0.5},
})

# m3: inclusion-exclusion count
LIM3 = 1_000_000
def count_div(lim, ds):
    return sum(1 for x in range(1, lim + 1) if any(x % d == 0 for d in ds))
# do it fast via inclusion-exclusion for the answer
def incl_excl(lim, ds):
    from itertools import combinations
    total = 0
    for r in range(1, len(ds) + 1):
        for combo in combinations(ds, r):
            l = 1
            for c in combo:
                l = l * c // math.gcd(l, c)
            total += ((-1) ** (r + 1)) * (lim // l)
    return total
DS3 = [6, 10, 15]
ans3 = LIM3 - incl_excl(LIM3, DS3)
tasks.append({
    "id": "v2-math-03", "category": "math_hard",
    "prompt": f"How many integers from 1 to {LIM3} inclusive are divisible by NONE of 6, 10, or 15? End with a line formatted exactly: ANSWER: N",
    "grader": {"type": "numeric", "expected": ans3, "tol": 0.5},
})

# m4: sum of digits of 2^E
E4 = 1000
tasks.append({
    "id": "v2-math-04", "category": "math_hard",
    "prompt": f"What is the sum of the decimal digits of 2^{E4} (2 raised to the power {E4})? End with a line formatted exactly: ANSWER: N",
    "grader": {"type": "numeric", "expected": sum(int(c) for c in str(2 ** E4)), "tol": 0.5},
})

# m5: modular exponentiation
A5, B5, M5 = 7, 644, 645
tasks.append({
    "id": "v2-math-05", "category": "math_hard",
    "prompt": f"Compute {A5}^{B5} mod {M5}. End with a line formatted exactly: ANSWER: N",
    "grader": {"type": "numeric", "expected": pow(A5, B5, M5), "tol": 0.5},
})

# ---------- CODING (harder; cases computed by reference impls) ----------

def ref_edit_distance(a, b):
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]; dp[0] = i
        for j in range(1, n + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i-1] != b[j-1]))
            prev = cur
    return dp[n]
ed_cases = [[["kitten", "sitting"], ref_edit_distance("kitten", "sitting")],
            [["", "abc"], ref_edit_distance("", "abc")],
            [["flaw", "lawn"], ref_edit_distance("flaw", "lawn")],
            [["intention", "execution"], ref_edit_distance("intention", "execution")]]
tasks.append({
    "id": "v2-code-01", "category": "code_hard",
    "prompt": "Write a Python function `edit_distance(a, b)` returning the Levenshtein edit distance (min single-character insertions, deletions, substitutions to turn a into b). Return ONLY a fenced python code block.",
    "grader": {"type": "code", "entry": "edit_distance", "cases": ed_cases},
})

def ref_min_coins(coins, amount):
    INF = float("inf")
    dp = [0] + [INF] * amount
    for a in range(1, amount + 1):
        for c in coins:
            if c <= a and dp[a - c] + 1 < dp[a]:
                dp[a] = dp[a - c] + 1
    return -1 if dp[amount] == INF else dp[amount]
mc_cases = [[[[1, 2, 5], 11], ref_min_coins([1,2,5], 11)],
            [[[2], 3], ref_min_coins([2], 3)],
            [[[1, 7, 10], 14], ref_min_coins([1,7,10], 14)],
            [[[186, 419, 83, 408], 6249], ref_min_coins([186,419,83,408], 6249)]]
tasks.append({
    "id": "v2-code-02", "category": "code_hard",
    "prompt": "Write a Python function `min_coins(coins, amount)` returning the fewest coins (unlimited supply of each denomination in the list) that sum to amount, or -1 if impossible. Return ONLY a fenced python code block.",
    "grader": {"type": "code", "entry": "min_coins", "cases": mc_cases},
})

def ref_lis(nums):
    import bisect
    tails = []
    for x in nums:
        i = bisect.bisect_left(tails, x)
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return len(tails)
lis_cases = [[[[10,9,2,5,3,7,101,18]], ref_lis([10,9,2,5,3,7,101,18])],
             [[[0,1,0,3,2,3]], ref_lis([0,1,0,3,2,3])],
             [[[7,7,7,7]], ref_lis([7,7,7,7])],
             [[[]], ref_lis([])]]
tasks.append({
    "id": "v2-code-03", "category": "code_hard",
    "prompt": "Write a Python function `lis_length(nums)` returning the length of the longest strictly increasing subsequence of the list nums. Return ONLY a fenced python code block.",
    "grader": {"type": "code", "entry": "lis_length", "cases": lis_cases},
})

def ref_longest_palindrome(s):
    if not s: return 0
    best = 1
    for center in range(len(s)):
        for lo, hi in ((center, center), (center, center + 1)):
            while lo >= 0 and hi < len(s) and s[lo] == s[hi]:
                best = max(best, hi - lo + 1); lo -= 1; hi += 1
    return best
lp_cases = [[["babad"], ref_longest_palindrome("babad")],
            [["cbbd"], ref_longest_palindrome("cbbd")],
            [["a"], ref_longest_palindrome("a")],
            [["forgeeksskeegfor"], ref_longest_palindrome("forgeeksskeegfor")]]
tasks.append({
    "id": "v2-code-04", "category": "code_hard",
    "prompt": "Write a Python function `longest_palindrome_len(s)` returning the length of the longest palindromic substring of s. Return ONLY a fenced python code block.",
    "grader": {"type": "code", "entry": "longest_palindrome_len", "cases": lp_cases},
})

# ---------- LONG-CONTEXT MULTI-HOP (larger context, answer computed) ----------

rng = random.Random(42)
FIRST = ["Ava","Ben","Cara","Dan","Eve","Finn","Gia","Hugo","Ivy","Jon","Kira","Leo","Mia","Noah","Ola","Pia","Quin","Ravi","Sara","Tom"]
CITIES = ["London","Leeds","Bristol","Cardiff","Glasgow","Bath","York","Hull","Derby","Ely"]
DEPTS = ["Sales","Ops","Data","Design","Legal"]
people = []
used = set()
for i in range(120):
    nm = rng.choice(FIRST) + f"_{i:03d}"
    people.append({"name": nm, "dept": rng.choice(DEPTS), "city": rng.choice(CITIES),
                   "salary": rng.randrange(30000, 95000, 500), "start": 2010 + rng.randrange(0, 16)})
doc = "\n".join(f"{p['name']} | dept={p['dept']} | city={p['city']} | salary={p['salary']} | start={p['start']}"
               for p in people)

# lc1: highest salary in a given dept -> return their city (multi-hop)
target_dept = "Data"
data_people = [p for p in people if p["dept"] == target_dept]
top = max(data_people, key=lambda p: p["salary"])
tasks.append({
    "id": "v2-lc-01", "category": "long_context_multihop",
    "prompt": f"Below is an employee table (one per line). Among employees in the {target_dept} department, find the one with the highest salary, then report the city that person is in.\n\n{doc}\n\nReply with a line formatted exactly: ANSWER: <city>",
    "grader": {"type": "exact", "expected": top["city"]},
})

# lc2: count employees in a department earning above a threshold (multi-hop: filter
# by dept AND salary across scattered rows). Pick dept+threshold yielding count 5..15.
c2_dept, c2_sal, cnt2 = None, None, None
for dept in DEPTS:
    for sal in range(45000, 80000, 5000):
        c = sum(1 for p in people if p["dept"] == dept and p["salary"] > sal)
        if 5 <= c <= 15:
            c2_dept, c2_sal, cnt2 = dept, sal, c
            break
    if cnt2 is not None:
        break
tasks.append({
    "id": "v2-lc-02", "category": "long_context_multihop",
    "prompt": f"Using the same table below, how many employees are in the {c2_dept} department AND earn more than {c2_sal}? Count carefully.\n\n{doc}\n\nReply with a line formatted exactly: ANSWER: N",
    "grader": {"type": "numeric", "expected": cnt2, "tol": 0.5},
})

# lc3: total salary of a department (aggregation over scattered rows)
c3_dept = "Legal"
sum3 = sum(p["salary"] for p in people if p["dept"] == c3_dept)
tasks.append({
    "id": "v2-lc-03", "category": "long_context_multihop",
    "prompt": f"Using the same table below, what is the exact total combined salary of everyone in the {c3_dept} department?\n\n{doc}\n\nReply with a line formatted exactly: ANSWER: N",
    "grader": {"type": "numeric", "expected": sum3, "tol": 0.5},
})

out = os.path.join(HERE, "golden_set_v2.json")
json.dump(tasks, open(out, "w"), indent=2)
print(f"wrote {len(tasks)} tasks to {out}")
print("context size of long-context prompt (chars):", len(doc))
for t in tasks:
    g = t["grader"]
    ans = g.get("expected", "[code:" + g.get("entry", "") + "]")
    print(f"  {t['id']:16} {t['category']:22} answer={ans}")
