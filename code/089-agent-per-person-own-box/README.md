# An agent on a box you own

The code behind two agents we run for real people: one runs a venue-hire studio's
bookings and enquiries, the other is a personal assistant for a busy household. Each
one lives on its **own** small VPS, on the owner's own account, reachable from
**Telegram** by text, screenshot, or voice note. No shared SaaS, no seat in someone
else's dashboard, no third party in the middle.

This folder is the generic, sanitised version of that setup. Steal what you need.

## What's here

| File | What it does |
|------|--------------|
| `bridge.py` | Long-polls Telegram, pipes each message to `claude --print --continue`, sends the reply back. Handles text, photos/screenshots (downloaded so the agent can `Read` them), voice notes (transcribed locally), and documents. Locked to a single owner. |
| `transcribe.py` | Turns a voice note into text with `faster-whisper`, running entirely on the box. |
| `install_whisper.sh` | One-shot install of ffmpeg + faster-whisper into a self-contained venv, with the model pre-cached. |
| `harden-vps.sh` | Locks the box down: key-only SSH, default-deny firewall, fail2ban, automatic security updates. Idempotent. |

## How it fits together

1. A person messages a Telegram bot.
2. `bridge.py` (running as a systemd service) checks they are the owner, turns their
   message into a prompt (downloading any photo/voice/file first), and runs Claude Code
   in a working directory on the box.
3. Claude Code does the work (builds, edits, reads the screenshot, answers) and the
   reply goes back to Telegram.

Because it shells out to `claude --print --continue`, the agent has a real shell, a
real filesystem, and a persistent conversation. It is not a chat wrapper, it is the
full coding agent, reachable from a phone.

## Run it

```bash
export BOT_TOKEN="123:abc"        # from @BotFather
export AGENT_NAME="Mac"           # what it calls itself
export ALLOWED_CHAT_IDS=""        # leave empty: first chat to message becomes the locked owner
python3 bridge.py
```

For voice notes: `bash install_whisper.sh` once, then voice just works.

Run it under systemd (`Restart=always`) so it survives reboots. Then harden the box:

```bash
sudo bash harden-vps.sh
```

## The one warning

`harden-vps.sh` turns off SSH password login. Make sure a **key-based** login works
first, or you will lock yourself out. The script validates the SSH config before
reloading and allows the SSH port through the firewall before enabling it, so a single
fumble will not strand you, but check your key works before you run it.

## Notes

- Transcription is local on purpose. Voice notes can be personal, and they never leave
  the owner's server.
- The owner-lock matters: the first chat to message becomes the owner and is written to
  `.owner_chat_ids`. Everyone else gets "this agent is private". Set `ALLOWED_CHAT_IDS`
  up front if you do not want the bootstrap.
- `--dangerously-skip-permissions` is used because the agent runs unattended on a box
  that is the owner's to begin with. That is a deliberate trade: it only makes sense
  *because* the box is single-tenant and hardened. Do not copy that flag onto a shared
  machine.
