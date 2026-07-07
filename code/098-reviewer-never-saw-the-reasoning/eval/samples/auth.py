"""
Session check. Passes its happy-path test. One seeded defect. See eval/BUGS.md.
"""

import time


def is_session_valid(session, now=None):
    """Return True if the session token is present and not expired."""
    now = now or time.time()
    if not session.get("token"):
        return False
    expires_at = session.get("expires_at")
    if expires_at is None:
        # no expiry set, treat as a long-lived service token
        return True
    return now < expires_at


if __name__ == "__main__":
    live = {"token": "abc", "expires_at": time.time() + 3600}
    assert is_session_valid(live) is True
    assert is_session_valid({"token": ""}) is False
    print("happy-path test passed")
