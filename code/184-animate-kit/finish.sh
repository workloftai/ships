#!/bin/bash
# Pull frames from the mini and encode MP4 + GIF + 1fps contact sheet. Run from the project folder.
# usage: NAME=my-explainer ./finish.sh
set -e
: "${RENDER_HOST:?set RENDER_HOST to the ssh target of your Blender Mac, e.g. user@mac-mini}"
JOB=${JOB:-$(basename "$PWD")}; NAME=${NAME:-$JOB}
rm -rf frames && mkdir -p frames
ssh "$RENDER_HOST" "cd ~/$JOB/out && find . -name 'f_*.png' | tar cf - -T -" | tar xf - -C frames
ffmpeg -v error -y -framerate 25 -i frames/f_%04d.png -c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p -movflags +faststart "$NAME-1280.mp4"
ffmpeg -v error -y -i "$NAME-1280.mp4" -vf "fps=1,scale=640:-1,tile=4x5" -frames:v 1 contact.png
# Bayer dither keeps camera-drift GIFs ~20MB; Telegram refuses >10MB as a photo, so zip or send the MP4
ffmpeg -v error -y -i "$NAME-1280.mp4" -vf "fps=20,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=full:max_colors=160[p];[b][p]paletteuse=dither=bayer:bayer_scale=5" -loop 0 "$NAME-960.gif"
ls -lh "$NAME-1280.mp4" "$NAME-960.gif" contact.png; echo "frames: $(ls frames | wc -l)"
