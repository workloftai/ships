#!/usr/bin/env bash
# Self-contained demo: build a short talking-head clip with real speech (via
# ffmpeg's built-in flite TTS) and deliberate silences, then run the full
# transcript-driven pipeline on it. No footage of your own required.
#
# Requires: ffmpeg (with libflite), python3, and `pip install faster-whisper`.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p demo

echo "[1/3] synthesising a talking-head clip with dead air baked in..."
ffmpeg -y -f lavfi -i "flite=text='This is a build in public update.':voice=slt" -t 3 demo/s1.wav 2>/dev/null
ffmpeg -y -f lavfi -i "flite=text='The transcript is the edit brain, not the pixels.':voice=slt" -t 4 demo/s2.wav 2>/dev/null
ffmpeg -y -f lavfi -i "flite=text='So the video simply follows the words.':voice=slt" -t 3 demo/s3.wav 2>/dev/null
ffmpeg -y -f lavfi -i "anullsrc=r=48000:cl=mono" -t 2 demo/sil.wav 2>/dev/null
ffmpeg -y -i demo/s1.wav -i demo/sil.wav -i demo/s2.wav -i demo/sil.wav -i demo/s3.wav \
  -filter_complex "[0][1][2][3][4]concat=n=5:v=0:a=1[a]" -map "[a]" demo/audio.wav 2>/dev/null
DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 demo/audio.wav)
ffmpeg -y -f lavfi -i "color=c=0x1a1a2e:s=1280x720:d=${DUR}" -i demo/audio.wav \
  -c:v libx264 -preset veryfast -crf 20 -c:a aac -b:a 160k -pix_fmt yuv420p -shortest demo/raw.mp4 2>/dev/null
echo "    raw clip: ${DUR}s (about 4s of it is silence)"

echo "[2/3] running the pipeline (transcribe -> tighten -> reframe -> caption -> normalise -> brand)..."
python3 vidkit.py pipeline demo/raw.mp4 -o demo/li-ready.mp4 --aspect 9:16 --title "Workloft"

echo "[3/3] result:"
ffprobe -v error -show_entries format=duration -show_entries stream=width,height \
  -of default=nw=1 demo/li-ready.mp4
echo "done -> demo/li-ready.mp4"
