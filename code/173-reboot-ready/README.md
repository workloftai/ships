# 173 · reboot-ready: what will not come back after a reboot

A server that has been up for months accumulates things that only work because
nobody has restarted it: a service that is running but was never enabled, a
container with no restart policy, a process someone started by hand in a
terminal. All fine until the reboot, then silently gone.

`reboot_ready.py` lists them before you reboot. Read-only, stdlib only, Linux
with systemd. It never restarts or reboots anything.

```bash
python3 reboot_ready.py                  # human report, exit 1 if anything won't return
python3 reboot_ready.py --json           # machine-readable
python3 reboot_ready.py --min-age-hours 0
python3 tests/test_classify.py
```

| check | what counts as "comes back" |
|---|---|
| kernel | reports running vs newest installed kernel, and `/var/run/reboot-required` |
| lifelines | ssh, tailscale, cron, docker enabled at boot (lose these and you cannot fix the rest remotely) |
| services | every running system service is enabled, socket-activated, or recreated by a systemd generator |
| containers | every running container has a restart policy (`always`, `unless-stopped`, `on-failure`) |
| orphans | long-lived processes outside any service or container (started by hand, or by a cron job) come back only if a cron line, `@reboot` or a periodic keepalive, names their script or working directory |

## First run on our box

A long-lived agent box: 32 running services, 18 containers, 2 cron-launched
long-lived processes. **One thing would not have come back**: a voice-agent
service that was running but had never been enabled.

The first version also cried wolf twice: `ssh.service` shows as disabled on
Ubuntu 24.04 because it is socket-activated, and `serial-getty@ttyS0` is
recreated at every boot by a generator. Both are now recognised.

## Limits

- It checks that things will be **started**, not that they will **work**: a
  service that starts and then fails on a missing mount still looks fine.
- A process spawned inside another service's cgroup is counted as that service.
- The cron match is a heuristic (script name or working directory in a cron
  line). A keepalive that starts something via an indirect wrapper may be missed,
  which errs towards "will not return", the safe side.
