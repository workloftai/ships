# bob-trace

Turn a detached background job into an inspectable trace, after the fact, by
reading what it already left on disk.

## The problem

Hook-based tracing only sees what runs inside the agent process. Long jobs are
often detached from that process on purpose: a watchdog kills unresponsive
foreground turns, and a long job sitting in a turn looks like a hang, so you
detach it to keep it safe. The moment you do, no hooks fire, no spans are
emitted, and the job is invisible to every trace, metric and dashboard you have.

The safety move and the invisibility are the same move. Your traces stop where
your processes leave the tree.

## The result

Pointed at 115 real jobs on our own fleet, the first run found 65% clean exits,
13 failures split into "killed by a signal" versus "exited non-zero", 101 US
dollars and 92,635 tokens sitting unattributed in logs, and one job that had
exited `rc=0` while seven of its cases had actually failed. An exit code is a
claim, not evidence.

## What it does

`bob_trace.py` reads a job's record and its log and derives:

- **lifecycle**: duration, timeout headroom, heartbeat stalls, whether a signal killed it
- **a single honest verdict**: `ok`, `done-with-errors`, `failed`, `timed-out`, `terminated`, `running`, with the reason in plain words
- **mined from the log**: error lines, retry / rate-limit markers, HTTP 429 and 5xx counts, model names, and tokens and cost when the job printed them

Then it renders that to the terminal, to a self-contained HTML card, or as an
OTLP span appended to an existing shipper spool so the job lands in the same
trace backend (we use Arize Phoenix) as everything else.

It is dependency-free (Python standard library only) and works on every job
already on disk.

## Run the demo

```bash
python3 demo.py
```

Runs against five bundled example jobs in `examples/jobs/` (one per verdict).
No network, no real fleet needed.

## Use it for real

```bash
# point at your own job records (defaults to /home/workloft/bob-bg/jobs)
export BOBBG_JOBS=/path/to/jobs

python3 bob_trace.py stats            # fleet-wide summary
python3 bob_trace.py list -n 20       # recent runs, health at a glance
python3 bob_trace.py show <job-id>    # full trace for one run
python3 bob_trace.py html <job-id>    # self-contained HTML trace card
python3 bob_trace.py emit --all       # append spans to the shipper spool
```

Each job's record is expected to be `<BOBBG_JOBS>/<id>.json` with a sibling
`<id>.log`. The JSON fields it reads: `id`, `label`, `cmd`, `status`, `rc`,
`timeout`, `started`, `ended`, `last_heartbeat`. See `examples/jobs/` for the
shape.

## The general shape

If you run detached work of any kind (background runners, queue workers, cron,
CI jobs), the lesson transfers: instrument what you can, and for the rest, trace
the artefacts the work leaves behind. A record and a log are enough to
reconstruct a trace that tells you far more than an exit code.

## Tests

```bash
python3 -m unittest test_bob_trace -v
```

## Licence

MIT. Part of [Workloft Ships](https://workloft.ai/ships/).
