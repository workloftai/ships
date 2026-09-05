"""
Keyword-based tier classifier for Larry's message routing.

Base classification (single shot, by keyword):
  Tier 1: FAQ / simple queries      → Gemini Flash-Lite ($0.25/$1.50)
  Tier 2: Standard tasks            → Sonnet 4.6 ($3/$15) with prompt caching
  Tier 3: Complex reasoning         → Opus 4.8 ($5/$25)

Escalation lane (see escalation.py), ABOVE the base tiers:
  Tier 4: Frontier / spike band     → GPT-6 Astra ($10/$50)
          Invoked ONLY on an escalation trigger, never by default:
            - task in Astra's proven spike band (browser/computer-use,
              cyber/vuln, frontier-maths, >512K context)
            - repeated tool-call failure at a lower tier
            - explicit low self-reported confidence at a lower tier
          Bounded by the £/$25-per-month guardrail on the tier3 OpenRouter key.

Why Astra is escalation-only: our own cost-per-solved-task eval (~/astra-eval)
showed Astra costs ~31% more than Opus on everyday work and only reaches
near-parity on hard tasks. It earns its 2x price only in the spike band.

Order: Tier 3 keywords win first, then Tier 1 (only if message is short),
otherwise default to Tier 2. Spike-band / escalation is layered on top by
escalation.py, which may override the base tier upward to Astra.
"""

TIER_3_KEYWORDS = {
    "refund", "complaint", "legal", "escalate", "dispute", "chargeback",
    "lawyer", "solicitor", "sue", "court", "ombudsman", "formal complaint",
    "gdpr", "data request", "subject access", "compensation",
}

TIER_1_KEYWORDS = {
    "hours", "open", "price", "address", "phone", "email", "menu",
    "stock", "hello", "hi", "hey", "thanks", "thank you", "ok", "okay",
    "yes", "no", "bye", "cheers", "when", "where", "how much", "cost",
    "website", "link", "contact", "directions",
}

MAX_TIER_1_WORDS = 12

# Astra's proven spike band → keyword hints per category. Presence of any of
# these routes a task straight to the Astra escalation lane (Tier 4). Keep this
# tight: over-matching here is what blows the budget on a $50/M model.
SPIKE_BAND_KEYWORDS = {
    "browser_computer_use": {
        "browse the", "navigate the", "click through", "fill in the form",
        "computer use", "control the browser", "log into the site",
        "multi-step ui", "screen recording", "automate the website",
    },
    "cyber_vuln": {
        "exploit", "vulnerability", "cve-", "reverse engineer", "fuzzing",
        "penetration test", "pentest", "buffer overflow", "privilege escalation",
        "malware analysis",
    },
    "frontier_maths": {
        "prove that", "theorem", "olympiad", "frontiermath", "combinatorial proof",
        "number-theoretic", "formal proof", "putnam",
    },
    "long_context": {
        ">512k", "entire codebase", "whole repository", "full transcript corpus",
        "across all documents", "million-token",
    },
}

ASTRA_TIER = 4
ASTRA_MODEL = "openai/gpt-6-astra"
ASTRA_MODEL_BATCH = "openai/gpt-6-astra:batch"

# Model IDs verified live via OpenRouter 2026-09-05 (dotted slugs route fine).
TIER_TO_MODEL = {
    1: "google/gemini-3.1-flash-lite-preview",
    2: "anthropic/claude-sonnet-4.6",
    3: "anthropic/claude-opus-4.8",
    ASTRA_TIER: ASTRA_MODEL,
}

# Legacy aliases — kept for backwards compat, all route through OpenRouter now
TIER_TO_OR_MODEL = TIER_TO_MODEL
TIER_TO_ANTHROPIC_MODEL = {}

TIER_TO_ALIAS = {
    1: "flash",
    2: "sonnet",
    3: "opus",
    ASTRA_TIER: "astra",
}

TIER_TIMEOUTS = {
    1: 60,
    2: 120,
    3: 600,
    ASTRA_TIER: 900,
}


def _word_match(keywords: set, text: str, words: list) -> bool:
    """Match keywords against text. Multi-word keywords use substring match,
    single-word keywords use word-boundary match to avoid false positives."""
    for k in keywords:
        if " " in k:
            if k in text:
                return True
        elif k in words:
            return True
    return False


def classify(msg: str) -> int:
    m = msg.lower().strip()
    # Strip punctuation for word-boundary matching
    import re
    clean = re.sub(r'[^\w\s]', '', m)
    words = clean.split()

    if _word_match(TIER_3_KEYWORDS, m, words):
        return 3

    if len(words) <= MAX_TIER_1_WORDS and _word_match(TIER_1_KEYWORDS, m, words):
        return 1

    return 2


def spike_band(msg: str):
    """
    Return the Astra spike-band category if the message clearly falls in it,
    else None. Substring match on lowered text (spike keywords are phrases, so
    substring is intentional and less prone to single-word false positives).
    """
    m = msg.lower()
    for category, phrases in SPIKE_BAND_KEYWORDS.items():
        for p in phrases:
            if p in m:
                return category
    return None


def route(msg: str) -> dict:
    """Return routing info for a message."""
    tier = classify(msg)
    return {
        "tier": tier,
        "model": TIER_TO_MODEL[tier],
        "alias": TIER_TO_ALIAS[tier],
        "timeout": TIER_TIMEOUTS[tier],
    }


if __name__ == "__main__":
    tests = [
        ("What are your opening hours?", 1),
        ("Hi", 1),
        ("I need to process a complex multi-step workflow involving three departments", 2),
        ("Can you help me with my order?", 2),
        ("I want a refund and I'm going to contact my solicitor", 3),
        ("This is a formal complaint about your service", 3),
        ("I want to make a GDPR subject access request", 3),
        ("How much does it cost?", 1),
        ("Can you analyse the quarterly revenue trends across all our local authority contracts and identify which ones are underperforming relative to the SLA benchmarks?", 2),
    ]

    print(f"{'Message':<80} {'Expected':>8} {'Got':>8} {'Pass':>6}")
    print("-" * 110)
    for msg, expected in tests:
        result = classify(msg)
        passed = result == expected
        display = msg[:77] + "..." if len(msg) > 80 else msg
        print(f"{display:<80} {expected:>8} {result:>8} {'  OK' if passed else ' FAIL':>6}")
