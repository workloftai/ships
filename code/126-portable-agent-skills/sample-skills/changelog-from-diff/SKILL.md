---
name: changelog-from-diff
description: Turn a git diff into one changelog entry written for the person who will read the release notes, not the person who wrote the code. Use before tagging a release or opening a PR.
---

# changelog-from-diff

Read the diff, write one entry.

- **One line, user-facing.** What changed for someone using the software, not
  which functions moved. "Uploads over 50MB no longer time out", not "raised the
  multipart threshold in upload.ts".
- **Lead with the verb.** Added / Fixed / Changed / Removed, then the thing.
- **Name the limitation if there is one.** If the fix only covers one case, say
  which. A changelog that hides the caveat is how surprises ship.
- **Skip the noise.** Formatting-only, lockfile, and comment-only diffs get no
  entry. If the whole diff is noise, say "no user-facing change".

Output just the entry. No headings, no "here is your changelog".
