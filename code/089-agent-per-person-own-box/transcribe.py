#!/usr/bin/env python3
"""Transcribe an audio file (a Telegram voice note) to text with faster-whisper.

Runs entirely on your own box, no audio leaves the server. Invoke with the whisper
venv python (see install_whisper.sh). Prints the transcript to stdout.

    whisper-venv/bin/python transcribe.py /path/to/voice.oga
"""
import sys
from faster_whisper import WhisperModel

# base.en: light and fast on CPU, good for clear English. Swap to "small.en" for
# more accuracy at a few times the cost, or a multilingual model ("base") if needed.
_model = WhisperModel("base.en", device="cpu", compute_type="int8")
segments, _info = _model.transcribe(sys.argv[1], beam_size=1)
print(" ".join(s.text.strip() for s in segments).strip())
