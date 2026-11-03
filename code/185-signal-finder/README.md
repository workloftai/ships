# signal-finder

Two small jobs, one file:

- **`playbook`**: turn hours of someone talking (podcasts, talks, posts) into one page you can use. Principles, steps, quotes with source and timestamp, and the places where the sources disagree.
- **`signal`**: find the single strongest, most recent thing a person said in public, and write a ten-second opener that proves you listened. If there is nothing real to reference, it says so and writes no opener.

```bash
pip install anthropic youtube-transcript-api   # the second one is optional
export ANTHROPIC_API_KEY=...

# no key needed: runs both modes on the bundled synthetic fixtures
python3 signal_finder.py demo

python3 signal_finder.py playbook "https://www.youtube.com/watch?v=LCEmiRjPEtQ" notes.md talk.vtt -o playbook.md
python3 signal_finder.py signal "Simon Willison" "Datasette" \
  --url "https://simonwillison.net/2026/Nov/3/qwen-can-interpret-model-weights/|2026-11-03" \
  --url "https://simonwillison.net/2026/Oct/3/default-hard-budget-caps/|2026-10-03"
```

Real output from both modes is in [`demo-output/`](demo-output/).

## How it works

`playbook`: each source is loaded as timed segments, chunked at about 24k characters, and each chunk goes to the model for up to 12 ideas, each with a quote. A second call merges everything into a playbook in which every line cites the item ids that support it.

`signal`: each source must mention the person by surname or it is skipped. The model proposes up to 5 things the person said or wrote per chunk. A second call picks the strongest, preferring recent, and writes the phrase that completes "I saw ...". The opener is a fixed template:

> Hey [Name], thanks for connecting. I saw [signal], which is exactly what I wanted to ask you about.

## The guards (in code, not just in the prompt)

- **Verbatim check.** Every quote the model returns is searched for in the source text (case and punctuation normalised). If it is not there word for word, it is dropped. The playbook footer tells you how many were dropped.
- **Timestamps come from the code.** They are the start of the caption segment where the quote was found, not a number the model made up.
- **No ghost citations.** Playbook lines citing ids that do not exist are removed. Quotes can only be rendered from verified items.
- **No invented personalisation.** No verified candidate, or the model picks `NONE`: no opener, exit code 3.
- **Auto-dub guard.** With the Supadata fetcher, if you ask for English and get another language back (YouTube now serves machine-dubbed tracks on some videos), the source is refused.

## Pluggable parts

| Part | Options |
|---|---|
| Model | `--model` (default `claude-opus-5-5`, or `SIGNAL_FINDER_MODEL`), `--effort` |
| YouTube transcripts | `--fetcher youtube-transcript-api` (default, free, often blocked from datacentre IPs), `supadata` (`SUPADATA_API_KEY`, has a free tier), `cmd` (`SIGNAL_FINDER_TRANSCRIPT_CMD="your-tool {url}"`) |
| Files | `.vtt`, `.srt`, `[mm:ss] text` lines, `.txt`, `.md`, `.html`. Optional `title:`, `date:` and `source:` header lines. |
| Search (signal) | `--url` (repeatable, `URL|YYYY-MM-DD` to set a date), or `--search exa` with `EXA_API_KEY` |
| Output | Markdown by default, `--json`, `-o file` |

## Limits, honestly

- Transcripts are machine-made. Names get mangled ("Andre Carpathy") and words get misheard. The verbatim check proves the quote is in the transcript, not that the person said it. Listen to the clip before you repeat it.
- Speaker attribution in a podcast is the model's judgement. A host's line can be mistaken for the guest's.
- "Most recent" is only as good as the dates you give it. Undated pages sort last.
- Public sources only. It reads what you point it at. Do not feed it anything you would not be comfortable quoting back to the person.
- A real run of the playbook mode on about 3 hours of audio (34k words) took 10 model calls and about 80k input tokens.

## Tests

```bash
python3 -m unittest discover -s tests
```

No network and no API key. Covers parsing, chunking, the verbatim check, and that an invented quote produces no opener.

Built by [Workloft](https://workloft.ai). MIT.
