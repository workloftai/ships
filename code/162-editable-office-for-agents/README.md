# Editable Office files for agents

An agent that only emits PDFs hands the reader a photograph of a document:
final, read-only, nothing to change. Often the person on the other end wants
the opposite. They want to change a number, add a row, cut a paragraph, and
forward it. That needs a real `.docx` or `.xlsx`.

This kit is the small, boring pipeline for that. Structured data in, editable
Office files out, validated against the OpenXML schema before they leave.

## Two halves, on purpose

- **Generate** from structured data with `python-docx` / `openpyxl`
  (`office_pack.py`). This is the right tool when the job is *build the file*.
- **Validate / inspect / render / agent-edit** with
  [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI) — a single self-contained
  binary (no Office install, no runtime). This is the right tool when the job
  is *read or edit a file someone else made*.

The interesting bit is that they check each other. OfficeCLI's `validate`
caught a real bug in the generator on the first run: a table-cell shading
element (`w:shd`) missing its required `val` attribute. Word renders it fine,
so a screenshot would have looked perfect. The schema check does not.

## Run it

```bash
# generation only (no OfficeCLI needed)
python3 build_demo.py

# also validate against OpenXML + render an HTML preview
OFFICECLI=./officecli python3 build_demo.py
```

Outputs land in `out/`:

- `alt-provision-placement-pack.docx` — a branded, fully editable Word document
- `placements-transport-tracker.xlsx` — an Excel tracker with **live formulas**
  (annual transport cost `=miles*trips*days*cost-per-mile`) and a `SUM` totals row
- `pack-preview.html` / `pack-preview.png` — OfficeCLI's own render of the pack

All demo data is fictional ("Riverside County Council"), so the kit runs
standalone with nothing confidential in it.

## The one gotcha

OfficeCLI keeps a document resident in memory after `create`/`open` for speed.
If you then rewrite that file on disk with another tool (as this kit does), a
read *through OfficeCLI* serves the stale in-memory copy until you `close` it.
`build_demo.py` closes the resident before validating. If your own pipeline
mixes direct-disk writes with OfficeCLI reads, do the same.

## Files

| File | What it is |
|---|---|
| `office_pack.py` | The generator: `build_docx(spec)` and `build_tracker(rows)` |
| `build_demo.py` | Builds the two demo deliverables, then validates + renders them |

## Get OfficeCLI

```bash
curl -sL -o officecli \
  https://github.com/iOfficeAI/OfficeCLI/releases/latest/download/officecli-linux-x64
chmod +x officecli
```

Pick the asset for your platform from the
[releases page](https://github.com/iOfficeAI/OfficeCLI/releases).
