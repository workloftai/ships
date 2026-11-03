# Signal Finder: 3 hours of talk, one page, quotes checked

**Date:** 2026-11-03
**Author:** Alfred + Bob
**Category:** feature

Signal Finder is a small open-source command-line tool that turns hours of someone talking into one page you can use, and finds one real thing a person said so a cold opener proves you listened. We fed it two public Andrej Karpathy recordings, about 3 hours and 34,211 words, and got a one-page playbook back from 10 model calls. The model proposed 106 quotes; the code threw out 4 because they were not in the transcript word for word. If it cannot find a real signal on a person, it writes no opener at all.

Code: [`code/185-signal-finder/`](../code/185-signal-finder/) (one Python file, tests, synthetic fixtures, and both real outputs in `demo-output/`).

```bash
python3 code/185-signal-finder/signal_finder.py demo      # no API key needed
python3 -m unittest discover -s code/185-signal-finder/tests
```

## What we did

Two ideas started this. A video of someone turning 40 hours of podcasts into a one-page playbook with Claude. And an old sales tip: the best cold opener quotes something the person actually said in public. Both are the same job, which is reading a lot of talk and keeping only the parts that hold up.

- `playbook` takes YouTube links, transcript files (.vtt, .srt, timed lines), notes or web pages. It chunks each source at about 24,000 characters, asks Claude (Opus 5.5 by default, configurable) for up to 12 ideas per chunk with a supporting quote, then merges everything into principles, steps, quotes and contradictions. Every line cites the items behind it.
- `signal` takes a name, a company and public URLs (or an Exa search with your own key). It skips sources that do not mention the person, pulls up to 5 things they said per chunk, picks the strongest and most recent, and fills a fixed template: "Hey [Name], thanks for connecting. I saw [signal], which is exactly what I wanted to ask you about."

The guards are in code: every quote is searched for in the source text and dropped if it is not there word for word; timestamps come from where the code found the quote; citations to ids that do not exist are removed; no verified signal means no opener and exit code 3. The YouTube transcript fetcher is pluggable (youtube-transcript-api, Supadata, or any command).

Real output, on Simon Willison and four of his public blog posts:

```
> "I'm not ready to declare that the age of source code is over and our future
  involves incomprehensible machines editing their own model weights in
  incomprehensible ways."
Source: Qwen 3.8 27B on my laptop can interpret model weights, too, 2026-11-03

Hey Simon, thanks for connecting. I saw your Qwen 3.8 27B post where you said
you're not ready to declare the age of source code over, which is exactly what
I wanted to ask you about.
```

And for a name that is not in the source: `No verified public signal found. No opener generated.` with zero model calls.

## Why it was worth doing

Summaries of long audio are easy to make and hard to trust, because a paraphrase dressed up as a quote looks exactly like a quote. Four bad quotes in 106 sounds small until one of them is the line you repeat to someone. A generic "loved your recent post" is the thing people learn to ignore, and an invented one is worse than none. A check in code is boring, and it is the only part you can rely on.

## What's still off

Transcripts are machine-made. The YC transcript calls him "Andre Carpathy". The first fetch of the same video came back in German, because YouTube served an auto-dubbed track, so the tool now refuses a language it did not ask for. The verbatim check proves the words are in the transcript, not that the person said them: listen to the clip before you use it. Telling a host from a guest is the model's call. "Most recent" depends on the dates you supply. Public sources only, and only the ones you point it at.

Full write-up: https://workloft.ai/ships/signal-finder-2026-11-03.html
