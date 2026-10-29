#!/bin/bash
# Render on the Mac mini (headless Blender, EEVEE). Run from the project folder.
# usage: ./push_render.sh still <pct> <frame>...   -> stills into ./out/
#        ./push_render.sh anim <pct> [start end]   -> frames into ~/<JOB>/out/ on the mini
# JOB defaults to the folder name; override with JOB=name.
set -e
: "${RENDER_HOST:?set RENDER_HOST to the ssh target of your Blender Mac, e.g. user@mac-mini}"
JOB=${JOB:-$(basename "$PWD")}
tar cf - scene.py tex | ssh "$RENDER_HOST" "mkdir -p ~/$JOB && tar xf - -C ~/$JOB"
MODE=$1; PCT=$2; shift 2
BL=/Applications/Blender.app/Contents/MacOS/Blender
if [ "$MODE" = still ]; then
  for fr in "$@"; do
    ssh "$RENDER_HOST" "cd ~/$JOB && $BL -b -P scene.py -- still $PCT $fr 2>&1 | grep -E 'Error|Traceback|Saved|line [0-9]' | tail -4"
  done
  mkdir -p out && ssh "$RENDER_HOST" "cd ~/$JOB/out && find . -name 'still_*.png' | tar cf - -T -" | tar xf - -C out
elif [ "$MODE" = inspect ]; then
  ssh "$RENDER_HOST" "cd ~/$JOB && $BL -b -P scene.py -- inspect 2>&1 | grep -E 'INSPECT|Error'"
else
  # zsh on the mini errors on unmatched globs: use find, never rm f_*
  ssh "$RENDER_HOST" "cd ~/$JOB && mkdir -p out && find out -name 'f_*.png' -delete; $BL -b -P scene.py -- anim $PCT $* > render.log 2>&1; tail -3 render.log"
fi
