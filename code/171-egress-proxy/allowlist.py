"""
Egress allowlist for the Workloft fleet, derived from evidence (a sweep of what
the agent code actually reaches, not a guess). Each entry is a base domain; the
guard treats a host as allowed if it equals an entry or is a subdomain of one.

Edit this file to change policy. Keep a purpose on every line, so a reviewer can
tell why an entry earns outbound access before anything is ever enforced.
"""

# category -> [(domain, purpose)]
ALLOWLIST = {
    "model_apis": [
        ("api.anthropic.com", "Claude models (direct)"),
        ("code.claude.com", "Claude Code"),
        ("api.openai.com", "OpenAI models + image gen"),
        ("openai.com", "OpenAI (redirect host)"),
        ("openrouter.ai", "routed models (deepseek, gpt, grok, kimi, qwen)"),
        ("generativelanguage.googleapis.com", "Gemini models"),
        ("www.googleapis.com", "Google auth/token"),
        ("api.x.ai", "Grok (xAI)"),
        ("api.z.ai", "GLM (Z.AI)"),
        ("mistral.ai", "Mistral models"),
    ],
    "backend": [
        ("supabase.co", "Supabase (audit log, app data, redvsred) all projects"),
    ],
    "messaging": [
        ("api.telegram.org", "Telegram bridge (Bob, Whitney, Mac agents)"),
    ],
    "vcs_publish": [
        ("github.com", "ships-oss public mirror"),
        ("gitlab.com", "expac + workloft.ai Pages"),
        ("api.typefully.com", "social queue"),
        ("typefully.com", "social queue (web)"),
    ],
    "own": [
        ("workloft.ai", "own site (curl-verify ships/notes)"),
    ],
    "research_read": [
        ("arxiv.org", "paper abstracts (arXiv-watch, /ahfu)"),
        ("huggingface.co", "model cards / datasets"),
        ("news.ycombinator.com", "HN digest"),
        ("hn.algolia.com", "HN search API"),
        ("api.daily.dev", "daily.dev digest"),
        ("reddit.com", "r/LocalLLaMA digest"),
        ("cursor.com", "Cursor changelog (Walt idea-scoring source)"),
    ],
    # Reached only by specific client / digest jobs. Kept explicit so they are
    # visible, not smuggled in under a broad rule.
    "client_context": [
        ("ico.org.uk", "ReferRoute/JN compliance refs"),
        ("gov.uk", "LA democracy + Ofsted refs (ReferRoute research)"),
        ("lgjobs.com", "LA outreach research"),
        ("linkedin.com", "post-target validation"),
    ],
}

# Explicitly NOT allowed, with a reason. The audit flags any of these that turn
# up in the code so they are a conscious decision, never a silent dependency.
DENYLIST_NOTES = {
    "bit.ly": "URL shortener, opaque redirect target, classic exfil channel",
}


def flat_domains():
    return [d for entries in ALLOWLIST.values() for (d, _p) in entries]


def is_allowed(host):
    """True if host equals or is a subdomain of an allowlisted base domain."""
    host = (host or "").strip().lower().rstrip(".")
    for base in flat_domains():
        if host == base or host.endswith("." + base):
            return True
    return False
