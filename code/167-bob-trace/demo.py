#!/usr/bin/env python3
"""
bob-trace demo — runs the tracer against five bundled example jobs.

No dependencies, no network, no real fleet needed. It points bob-trace at the
example job records in examples/jobs/ and prints the fleet summary, the run
list, and a full trace for the one job that lies: it exited rc=0 but had
failing cases inside.

    python3 demo.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
# point the tracer at the bundled fixtures instead of a real bob-bg dir
os.environ["BOBBG_JOBS"] = os.path.join(HERE, "examples", "jobs")

import bob_trace as bt  # noqa: E402  (env must be set before import reads it)

# bob_trace read JOBS_DIR at import time; refresh it from the env we just set
bt.JOBS_DIR = os.environ["BOBBG_JOBS"]


def rule(title):
    print("\n" + title)
    print("-" * len(title))


def main():
    ids = bt._all_job_ids()

    rule("FLEET SUMMARY  (bob-trace stats)")
    print(bt.render_stats([bt.build_trace(i) for i in ids]))

    rule("RUN LIST  (bob-trace list)")
    print(bt.render_list([bt.build_trace(i) for i in ids][::-1], use_colour=True))

    rule("THE ONE THAT LIED  (bob-trace show 20260902-090000)")
    print("  exit code said pass. the run had not.\n")
    print(bt.render_show(bt.build_trace("20260902-090000"), use_colour=True))

    rule("PIPE INTO A TRACE BACKEND  (bob-trace emit)")
    print("  in production this appends OTLP spans to the shipper spool, which\n"
          "  drains to Phoenix. here we just show the span bob-trace would emit:")
    import json
    span = bt.to_spans(bt.build_trace("20260905-140000"))[0]
    print(json.dumps({k: span[k] for k in ("name", "kind", "status_error")}, indent=2))
    print("  attrs:", json.dumps(span["attrs"], indent=2)[:600], "...")


if __name__ == "__main__":
    main()
