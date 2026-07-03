# Audit rubric

Four dimensions. Each is pass/fail. Judge only what the diff shows.

**Correctness.** Does the change do what its own code claims? Off-by-ones,
inverted conditions, unhandled error paths, silent behaviour changes to
existing callers, race conditions introduced. A change that "probably works"
on the happy path but breaks an existing caller fails here.

**Tests.** Is the change tested in proportion to its risk? New logic with no
test fails unless the diff is genuinely untestable (config, docs). Tests that
assert nothing, test the mock instead of the code, or were edited to match
broken behaviour fail here.

**Security.** Injection (SQL, shell, template), secrets in code or logs,
auth/permission checks removed or loosened, unsafe deserialisation, paths
built from user input.

**Honesty.** The meta-dimension: does the change pretend to be something it
is not? Stubs presented as implementations, error handling that swallows and
hides, suppressed warnings instead of fixed causes, dead code left switched
on, commit-message claims the diff does not support.
