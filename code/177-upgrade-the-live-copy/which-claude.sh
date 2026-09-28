#!/usr/bin/env bash
# which-claude.sh: list every Claude Code install on this box, its version,
# and which one each running claude process is actually using.
# Read-only. Run it before and after an upgrade.
set -u

installs=$(
  {
    command -v -a claude 2>/dev/null
    ls "$HOME"/.local/bin/claude "$HOME"/.local/node_modules/.bin/claude \
       /usr/bin/claude /usr/local/bin/claude \
       "$HOME"/.npm-global/bin/claude "$HOME"/.bun/bin/claude 2>/dev/null
  } | while read -r p; do [ -e "$p" ] && readlink -f "$p"; done | sort -u
)

echo "== installs found"
for real in $installs; do
  v=$("$real" --version 2>/dev/null | head -1)
  printf '%-72s %s\n' "$real" "${v:-?}"
done

echo
echo "== running processes using one of those installs"
for d in /proc/[0-9]*; do
  exe=$(readlink -f "$d/exe" 2>/dev/null) || continue
  case " $(echo $installs) " in *" $exe "*) ;; *) continue ;; esac
  cmd=$(tr '\0' ' ' < "$d/cmdline" 2>/dev/null | cut -c1-80)
  printf '%-8s %s\n         %s\n' "${d#/proc/}" "$exe" "$cmd"
done

echo
echo "If the process you care about points at a different install from the one"
echo "you just upgraded, you upgraded the wrong copy."
