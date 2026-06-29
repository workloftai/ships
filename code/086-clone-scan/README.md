# 086 · clone-scan

Find what a freshly-cloned repo will **execute** before you let an agent (or
yourself) run a normal command in it.

Mozilla's 0din team showed AI coding agents getting owned by repos that look
clean: no obvious malware, nothing in the README a reviewer flinches at. The
trick is that the repo runs you the moment you do something ordinary.
`npm install` fires a `postinstall`. Opening the folder triggers a `tasks.json`
task set to run on folder-open. A devcontainer build runs a `postCreateCommand`.
The payload never had to talk anyone into anything. It waited for normal
behaviour.

`clone-scan` is a static pre-flight for exactly that surface. Point it at a repo
you do not trust, before the first install, build, or editor-open.

## What it checks

- npm/yarn/pnpm `preinstall` / `install` / `postinstall` (and the root repo's
  `prepare`, which also fires on `npm install`)
- VS Code `.vscode/tasks.json` tasks with `runOptions.runOn: "folderOpen"`
- devcontainer `postCreateCommand`, `onCreateCommand`, `postStartCommand`, etc.
- Husky / `.githooks` git hooks
- `Makefile`, `justfile`, `setup.py`
- **supply chain:** how many dependency packages under `node_modules` run
  install hooks. Any one of them executes arbitrary code on `npm install`.

A hook that merely exists is reported as the surface it is (medium). A hook whose
payload pipes a download into a shell, decodes base64 and runs it, opens a
reverse shell, or reaches for secrets is **HIGH**, and the tool exits non-zero so
an automated caller stops.

## Design

- Pure static parsing. It never executes anything it finds, makes no network
  call, and runs no LLM, so the scanner itself cannot be injected by the repo.
- Findings carry a rule id, severity, file, and a short sanitized snippet, never
  a re-emitted payload blob a downstream guardian would have to ingest.
- Fails closed on a real find, open on its own errors: a malformed file is
  reported, not crashed on, so a broken scan never wedges the caller.

## Usage

```bash
python3 clone_scan.py /path/to/repo          # scan one or more repo roots
python3 clone_scan.py --json /path/to/repo   # machine-readable output
python3 clone_scan.py --no-deps /path/to/repo  # skip the supply-chain count
python3 clone_scan.py --demo                 # self-test: weaponised vs clean repo
```

Exit: `0` clean / only-medium, `1` HIGH finding, `2` usage error.

## What it does not do

It is a signature scanner. It catches the shapes it was taught and will miss a
novel obfuscation or a payload assembled at runtime from innocent pieces. It
reads the manifest, not the code the manifest calls, so a tidy `postinstall` that
runs a malicious `scripts/build.js` reads as surface, not as a weapon. "Surface"
is not "safe". It means code runs here, go and look. It is a tripwire and a map,
not a clean bill of health. For anything you genuinely do not trust, it tells you
where to point the sandbox, it does not replace it.

Part of a family: [074 instruction-scan](../074-agents-locked-down) screens the
text an agent reads, [034 trojan-scan] watches persisted state, this watches the
execution surface.

MIT. Steal what you want.
