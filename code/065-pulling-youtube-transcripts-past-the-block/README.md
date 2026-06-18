# yt-transcript

Pull a YouTube transcript from a link, resilient to YouTube blocking your server's IP.

```bash
python3 yt_transcript.py "https://youtu.be/VIDEOID"          # plain text
python3 yt_transcript.py VIDEOID --json                       # route + words + transcript
```

Tries, in order:
1. `youtube-transcript-api` (works only if the host isn't IP-blocked)
2. Invidious caption mirrors (several public instances)
3. Supadata API (maintained backstop, needs `SUPADATA_API_KEY`)

As of June 2026, routes 1 and 2 are blocked from datacentre IPs, so route 3
carries it. Supadata has a free tier (100/month). Set `SUPADATA_API_KEY` in the
environment, or in a `.env` the script reads.

Built by Workloft (https://workloft.ai). MIT.
