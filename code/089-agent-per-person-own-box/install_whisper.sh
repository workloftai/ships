#!/usr/bin/env bash
# Install local voice-note transcription for the bridge: ffmpeg + faster-whisper
# in a self-contained venv, and pre-cache the model so the first voice note is fast.
# Run from the bridge directory. Nothing leaves the box.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

sudo apt-get update -y
sudo apt-get install -y ffmpeg python3-venv

python3 -m venv "$HERE/whisper-venv"
"$HERE/whisper-venv/bin/pip" install -U pip
"$HERE/whisper-venv/bin/pip" install faster-whisper

# Pre-download + cache the model (base.en) so the first real transcription is quick.
"$HERE/whisper-venv/bin/python" -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8'); print('model cached')"

echo "WHISPER_READY"
