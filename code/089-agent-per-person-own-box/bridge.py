#!/usr/bin/env python3
"""Telegram <-> Claude Code bridge: give one person their own agent on their own box.

Long-polls Telegram, pipes each message to `claude --print --continue` in a working
directory, and sends the reply back. Handles text, photos/screenshots (downloaded so
the agent can Read them), voice notes (transcribed locally with faster-whisper, see
transcribe.py) and documents. One ongoing conversation, runs as a systemd service.

The agent is locked to a single owner: the first chat to message after start becomes
the owner (or pre-set via ALLOWED_CHAT_IDS), so nobody else can drive it.

Env:
  BOT_TOKEN         Telegram bot token from @BotFather              [required]
  ALLOWED_CHAT_IDS  comma-separated chat ids allowed to use it      [optional]
  AGENT_NAME        what the agent calls itself in the hello        [default "your agent"]
  WORKSPACE         working dir for claude                          [default ./workspace]

This is the generic version of the bridge behind Workloft's Mac and Whitney agents.
Nothing here phones home; transcription runs on your own box.
"""
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{TOKEN}"
AGENT_NAME = os.environ.get("AGENT_NAME", "your agent")
WORKSPACE = os.environ.get("WORKSPACE", os.path.join(os.getcwd(), "workspace"))
HERE = os.path.dirname(os.path.abspath(__file__))
OWNER_FILE = os.path.join(HERE, ".owner_chat_ids")
INBOX = os.path.join(HERE, "inbox")
WHISPER_PY = os.path.join(HERE, "whisper-venv/bin/python")
TRANSCRIBE_PY = os.path.join(HERE, "transcribe.py")
CLAUDE_TIMEOUT = 1800  # 30 min: builds can be long


def _allowed():
    ids = set(x.strip() for x in os.environ.get("ALLOWED_CHAT_IDS", "").split(",") if x.strip())
    if os.path.exists(OWNER_FILE):
        ids |= set(l.strip() for l in open(OWNER_FILE) if l.strip())
    return ids


def _remember_owner(chat_id):
    with open(OWNER_FILE, "a") as f:
        f.write(str(chat_id) + "\n")


def send(chat_id, text):
    # Telegram caps messages at 4096 chars; chunk well under it.
    for i in range(0, len(text), 3500):
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[i:i + 3500]}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(API + "/sendMessage", data=data), timeout=30)
        except Exception as e:
            print("send error:", e, flush=True)


def typing(chat_id):
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "action": "typing"}).encode()
        urllib.request.urlopen(urllib.request.Request(API + "/sendChatAction", data=data), timeout=10)
    except Exception:
        pass


def download(file_id, default_ext):
    """Download a Telegram file by id into INBOX; return the local path."""
    os.makedirs(INBOX, exist_ok=True)
    meta_url = API + "/getFile?" + urllib.parse.urlencode({"file_id": file_id})
    meta = json.loads(urllib.request.urlopen(meta_url, timeout=30).read())
    remote = meta["result"]["file_path"]
    ext = os.path.splitext(remote)[1] or default_ext
    dest = os.path.join(INBOX, f"{int(time.time() * 1000)}{ext}")
    with urllib.request.urlopen(FILE_API + "/" + remote, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def transcribe(path):
    if not os.path.exists(WHISPER_PY):
        return "(voice transcription isn't installed yet, type your message for now)"
    try:
        r = subprocess.run([WHISPER_PY, TRANSCRIBE_PY, path],
                           capture_output=True, text=True, timeout=300)
        out = (r.stdout or "").strip()
        if out:
            return out
        return "(could not transcribe: " + (r.stderr.strip()[:200] or "no speech detected") + ")"
    except Exception as e:
        return f"(transcription failed: {e})"


def build_prompt(msg):
    """Turn a Telegram message into a text prompt for the agent. Returns None to ignore."""
    caption = (msg.get("caption") or "").strip()

    if "text" in msg:
        return msg["text"].strip()

    if "photo" in msg:
        file_id = msg["photo"][-1]["file_id"]  # largest size
        try:
            path = download(file_id, ".jpg")
        except Exception as e:
            return f"[The owner sent a photo but it could not be downloaded: {e}]"
        p = (f"[The owner sent you a photo / screenshot, saved at:\n{path}\n"
             f"Open it with your Read tool to see what's in it, then respond.]")
        return p + (f"\n\nCaption: {caption}" if caption else "")

    if "voice" in msg or "audio" in msg:
        media = msg.get("voice") or msg.get("audio")
        try:
            path = download(media["file_id"], ".oga")
        except Exception as e:
            return f"[The owner sent a voice note but it could not be downloaded: {e}]"
        text = transcribe(path)
        p = "[The owner sent a voice note. Transcript (auto, may have minor errors):]\n\n" + text
        return p + (f"\n\n(caption: {caption})" if caption else "")

    if "document" in msg:
        doc = msg["document"]
        try:
            path = download(doc["file_id"], "")
        except Exception as e:
            return f"[The owner sent a file but it could not be downloaded: {e}]"
        if doc.get("mime_type", "").startswith("image/"):
            p = f"[The owner sent an image, saved at:\n{path}\nOpen it with your Read tool.]"
        else:
            p = (f"[The owner sent a file ({doc.get('file_name', 'unnamed')}), saved at:\n{path}\n"
                 f"Read it if relevant.]")
        return p + (f"\n\nCaption: {caption}" if caption else "")

    return None


def ask_claude(prompt):
    try:
        r = subprocess.run(
            ["claude", "--print", "--continue", "--dangerously-skip-permissions"],
            input=prompt, capture_output=True, text=True, cwd=WORKSPACE, timeout=CLAUDE_TIMEOUT,
        )
        out = (r.stdout or "").strip()
        if not out and r.stderr:
            out = "(agent error) " + r.stderr.strip()[:500]
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "That took too long and timed out, try breaking it into a smaller step."
    except Exception as e:
        return f"(bridge error) {e}"


def main():
    os.makedirs(WORKSPACE, exist_ok=True)
    offset = None
    print("bridge up. workspace=", WORKSPACE, "allowed=", _allowed() or "(first chat wins)", flush=True)
    while True:
        try:
            params = {"timeout": 50}
            if offset is not None:
                params["offset"] = offset
            url = API + "/getUpdates?" + urllib.parse.urlencode(params)
            data = json.loads(urllib.request.urlopen(url, timeout=70).read())
        except Exception as e:
            print("poll error:", e, flush=True)
            time.sleep(5)
            continue
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue
            chat_id = str(msg["chat"]["id"])
            allowed = _allowed()
            if not allowed:
                # Bootstrap: first person to message becomes the locked owner.
                _remember_owner(chat_id)
                send(chat_id, f"Hi, I'm {AGENT_NAME}, now linked to you. "
                              "Tell me what you'd like to work on and I'll get going.")
                continue
            if chat_id not in allowed:
                send(chat_id, "Sorry, this agent is private.")
                continue
            prompt = build_prompt(msg)
            if prompt is None:
                continue
            typing(chat_id)
            send(chat_id, ask_claude(prompt))


if __name__ == "__main__":
    main()
