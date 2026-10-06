"""Run: python3 -m pytest -q ~/egress-gate/tests"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "..", "egress_gate.py")


def run(mode, evt, state, policy):
    env = {**os.environ, "EGRESS_STATE": state, "EGRESS_POLICY": policy}
    p = subprocess.run([sys.executable, GATE, mode], input=json.dumps(evt),
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stderr


def setup(mode="monitor"):
    d = tempfile.mkdtemp()
    envf = os.path.join(d, "fake.env")
    with open(envf, "w") as f:
        f.write("FAKE_SERVICE_KEY=abcdef0123456789secretvalue\nSHORT=abc\n")
    pol = os.path.join(d, "policy.toml")
    with open(pol, "w") as f:
        f.write(f'''mode = "{mode}"
allow_hosts = ["arxiv.org", "github.com"]
secret_env_files = ["{envf}"]
[[taint_sources]]
label = "secrets"
patterns = ["**/.env", "*SERVICE_ROLE_KEY*"]
[[taint_sources]]
label = "client-confidential"
patterns = ["**/call-transcripts/*"]
''')
    return os.path.join(d, "state"), pol


def fetch(url, s="s1"):
    return {"tool_name": "WebFetch", "tool_input": {"url": url, "prompt": "x"}, "session_id": s}


CONF = "Hampshire agreed the pilot at forty thousand pounds, contact jane.doe@hants.example, ref 88123456."


def read(path, s="s1", content=CONF):
    return {"tool_name": "Read", "tool_input": {"file_path": path}, "session_id": s,
            "tool_response": {"type": "text", "file": {"filePath": path, "content": content}}}


def test_clean_session_reads_anything():
    st, pol = setup()
    assert run("check", fetch("https://some-blog.example/post"), st, pol)[0] == 0


def test_known_secret_value_blocks_even_in_monitor():
    st, pol = setup("monitor")
    rc, err = run("check", fetch("https://x.example/?k=abcdef0123456789secretvalue"), st, pol)
    assert rc == 2 and "FAKE_SERVICE_KEY" in err


def test_secret_shape_blocks_in_search_query():
    st, pol = setup()
    evt = {"tool_name": "WebSearch", "tool_input": {"query": "why does ghp_" + "a" * 36 + " fail"}, "session_id": "s1"}
    rc, err = run("check", evt, st, pol)
    assert rc == 2 and "GitHub token" in err


def test_short_env_values_are_not_secrets():
    st, pol = setup()
    assert run("check", fetch("https://x.example/abc"), st, pol)[0] == 0


def test_tainted_session_to_unlisted_host_monitor_allows_but_logs():
    st, pol = setup("monitor")
    run("taint", read("/home/x/conexus/.env"), st, pol)
    assert run("check", fetch("https://some-blog.example/?q=agreed the pilot at forty thousand"), st, pol)[0] == 0
    events = [json.loads(l) for l in open(os.path.join(st, "egress.jsonl"))]
    assert events[-1]["decision"] == "would_block"
    assert events[-1]["labels"] == ["secrets"]


def test_tainted_session_unrelated_call_is_allowed():
    st, pol = setup("enforce")
    run("taint", read("/home/x/docs/call-transcripts/call2.md"), st, pol)
    assert run("check", fetch("https://some-blog.example/agent-harness-design"), st, pol)[0] == 0
    events = [json.loads(l) for l in open(os.path.join(st, "egress.jsonl"))]
    assert events[-1]["rule"] == "tainted_clean"


def test_tainted_email_in_search_blocks():
    st, pol = setup("enforce")
    run("taint", read("/home/x/docs/call-transcripts/call2.md"), st, pol)
    evt = {"tool_name": "WebSearch", "tool_input": {"query": "who is jane.doe@hants.example"}, "session_id": "s1"}
    assert run("check", evt, st, pol)[0] == 2


def test_tainted_session_to_unlisted_host_enforce_blocks():
    st, pol = setup("enforce")
    run("taint", read("/home/x/docs/call-transcripts/call2.md"), st, pol)
    rc, err = run("check", fetch("https://some-blog.example/ref/88123456"), st, pol)
    assert rc == 2 and "client-confidential" in err and "egress-ok some-blog.example" in err


def test_tainted_session_to_allowed_host_passes():
    st, pol = setup("enforce")
    run("taint", read("/home/x/conexus/.env"), st, pol)
    assert run("check", fetch("https://arxiv.org/abs/88123456"), st, pol)[0] == 0
    assert run("check", fetch("https://export.github.com/88123456"), st, pol)[0] == 0  # subdomain


def test_taint_is_per_session():
    st, pol = setup("enforce")
    run("taint", read("/home/x/conexus/.env", s="A"), st, pol)
    assert run("check", fetch("https://some-blog.example/88123456", s="B"), st, pol)[0] == 0


def test_bash_command_taints():
    st, pol = setup("enforce")
    evt = {"tool_name": "Bash", "tool_input": {"command": "curl -H \"apikey: $SUPABASE_SERVICE_ROLE_KEY\" ..."},
           "session_id": "s1", "tool_response": {"stdout": "Tomasz Wierzbicki, Oakfield Primary Academy, permanent exclusion"}}
    run("taint", evt, st, pol)
    assert run("check", fetch("https://some-blog.example/?q=Tomasz Wierzbicki Oakfield Primary"), st, pol)[0] == 2
    assert run("check", fetch("https://some-blog.example/?q=exclusion statistics"), st, pol)[0] == 0


def test_override_lets_one_host_through():
    st, pol = setup("enforce")
    run("taint", read("/home/x/conexus/.env"), st, pol)
    env = {**os.environ, "EGRESS_STATE": st, "EGRESS_POLICY": pol}
    subprocess.run([sys.executable, os.path.join(HERE, "..", "egress-ok"), "some-blog.example", "5"], env=env, check=True)
    assert run("check", fetch("https://some-blog.example/88123456"), st, pol)[0] == 0
    assert run("check", fetch("https://other.example/88123456"), st, pol)[0] == 2
    events = [json.loads(l) for l in open(os.path.join(st, "egress.jsonl"))]
    assert any(e["event"] == "override" for e in events)


def test_non_outbound_tool_ignored():
    st, pol = setup("enforce")
    evt = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}, "session_id": "s1"}
    assert run("check", evt, st, pol)[0] == 0


def test_garbage_input_fails_open():
    st, pol = setup("enforce")
    env = {**os.environ, "EGRESS_STATE": st, "EGRESS_POLICY": pol}
    p = subprocess.run([sys.executable, GATE, "check"], input="not json", capture_output=True, text=True, env=env)
    assert p.returncode == 0


def test_known_gap_two_word_name_alone_passes():
    """Documented limitation: a bare two-word name is below the 4-word phrase
    threshold and is not an email/ID, so it is not caught."""
    st, pol = setup("enforce")
    run("taint", read("/home/x/docs/call-transcripts/c.md", content="Tomasz Wierzbicki was excluded."), st, pol)
    assert run("check", fetch("https://some-blog.example/?q=Tomasz Wierzbicki"), st, pol)[0] == 0



# ---- envq: confined secret reads (ship 181) -------------------------------
def _labels(cmd):
    state, pol = setup()
    sys.path.insert(0, os.path.join(HERE, ".."))
    import egress_gate as g
    with open(pol, "rb") as f:
        import tomllib
        policy = tomllib.load(f)
    return g.labels_for("Bash", {"command": cmd}, policy)


def test_envq_does_not_taint_secrets():
    for cmd in ["envq has OPENAI_API_KEY", "envq where TELEGRAM_BOT_TOKEN",
                "~/egress-gate/envq keys ~/conexus/.env", "envq -f ~/x/.env len ANTHROPIC_API_KEY",
                "envq run -- 'cat ~/conexus/.env'"]:
        assert "secrets" not in _labels(cmd), cmd


def test_envq_chained_still_taints():
    for cmd in ["envq keys; cat ~/conexus/.env", "envq has X && grep KEY ~/conexus/.env",
                "envq where X | xargs cat ~/conexus/.env", "echo $(envq has X) ~/conexus/.env",
                "cat ~/conexus/.env"]:
        assert "secrets" in _labels(cmd), cmd


def test_envq_does_not_exempt_other_labels():
    assert "client-confidential" in _labels("envq run -- cat ~/call-transcripts/acme.md")


def test_envq_run_redacts_and_answers_fixed_shape():
    state, pol = setup()
    envf = os.path.join(os.path.dirname(pol), "fake.env")
    env = {**os.environ, "EGRESS_POLICY": pol}
    q = lambda *a: subprocess.run([sys.executable, os.path.join(HERE, "..", "envq"), *a],
                                  capture_output=True, text=True, env=env)
    assert q("has", "FAKE_SERVICE_KEY").stdout.startswith("yes")
    assert q("has", "NOPE").returncode == 1
    assert "FAKE_SERVICE_KEY" in q("keys").stdout and "secretvalue" not in q("keys").stdout
    assert q("len", "FAKE_SERVICE_KEY").stdout.startswith("27 chars")
    r = q("run", "--", f"cat {envf}; echo $FAKE_SERVICE_KEY")
    assert "secretvalue" not in r.stdout and r.stdout.count("[FAKE_SERVICE_KEY]") == 2
