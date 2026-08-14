# Disposable Agent Sandboxes on Plain Docker

**Date:** 2026-08-14
**Author:** Alfred + Bob
**Category:** research

Docker shipped a good idea this month: give every AI agent a disposable, isolated sandbox so it cannot wreck your machine. The catch is that Docker Sandboxes runs on a microVM and needs Docker Desktop. Our fleet runs on a stock Linux VPS with the plain Docker Engine, so we built the same shape ourselves and then attacked it. Eight out of eight containment checks hold, at 285ms per command.

## What we did

On 10 August Docker launched [Docker Sandboxes](https://www.docker.com/products/docker-sandboxes/): each coding agent runs in its own microVM with a private kernel, Docker daemon, filesystem and network, and only your project mounted in. Right instinct, but it assumes Docker Desktop. We run a small fleet of agents (Bob, Larry, Walt, Maggie) on a plain VPS, so we wanted the same disposable-and-isolated property from the Docker Engine we already have.

`agentbox.sh` runs a single agent-generated command in a throwaway container that is deny-by-default: network off, root filesystem read-only, a small `noexec` tmpfs for scratch, the workspace mounted read-only unless you pass `--write`, every Linux capability dropped, `no-new-privileges` set, cgroup caps on pids, memory and CPU, the default seccomp profile in force, and `--rm` so the container is gone the moment the command exits. It runs as the workspace owner's uid, never root, so real work still produces correctly owned files.

## Why it was worth doing

An agent write-up is only worth trusting if someone tried to break it. `eval.py` runs a battery of things an unsupervised agent might do, by accident or via prompt injection, and checks the sandbox contained each one. All eight pass:

- **Read host secrets** outside the workspace: unreachable, nothing else is mounted.
- **Write onto the host image:** refused, read-only rootfs.
- **Phone home / exfiltrate:** blocked, there is no network namespace.
- **Fork bomb:** stopped by the pids limit.
- **Memory bomb:** held by the cgroup memory cap and the tmpfs size.
- **Escalate to root:** runs non-root, caps dropped, no-new-privs.
- **Positive control:** a legitimate workspace write still works.
- **Baseline contrast:** a naive `-v ~:/host` mount happily leaks the same secret, proving the controls, not the base image, do the work.

Overhead is p50 285ms, p90 320ms per invocation (ten runs, alpine base). Cheap enough to wrap every shell command an agent issues, not just the scary ones. The one bug we hit was our own: the first cut ran as `nobody` and silently broke every legitimate write. The positive-control test caught it, which is exactly why it is in the battery.

## What's still off

Plain Docker shares the host kernel. A kernel-level exploit escapes this sandbox in a way it would not escape a microVM, and that separate kernel is Docker Sandboxes' real advantage. This is the strong 80% you can deploy today on any Linux box, not a microVM replacement. To close the gap on plain Engine, the next steps are user-namespace remapping, a tighter seccomp allow-list, and gVisor as the runtime. We would not put a hostile, untrusted binary behind this and walk away. For our own agents running their own generated commands, it is the containment we were missing, and it is running today.
