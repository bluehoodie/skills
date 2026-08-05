#!/usr/bin/env bash
# survey.sh — which projects need consolidation, and marking them done.
#
#   survey.sh list [cap]      print dirty project dirs, newest activity first
#   survey.sh stamp <dir>     mark one project as consolidated
#
# A project is dirty when it holds a transcript newer than its marker, or has
# no marker at all. Markers are per-project on purpose: a single shared
# watermark plus a cap silently orphans every project the cap drops, because
# stamping it makes their transcripts old too. Reproduced during design; the
# "pass 2" case in test-survey.sh is that bug.
#
# Env overrides exist for the test fixture and the status command:
#   DREAM_PROJECTS  default ~/.claude/projects
#   DREAM_SEEN      default ~/.claude/dream/seen
#   DREAM_HOST      slug to exclude; default = slug of $PWD
set -u

PROJECTS="${DREAM_PROJECTS:-$HOME/.claude/projects}"
SEEN="${DREAM_SEEN:-$HOME/.claude/dream/seen}"

seed_if_cold() {
  # First ever run: mark every existing project 7 days back, so a fresh install
  # consolidates the last week rather than every project on the machine.
  [ -d "$SEEN" ] && return 0
  mkdir -p "$SEEN"
  local stamp
  stamp=$(date -v-7d +%Y%m%d%H%M 2>/dev/null || date -d '7 days ago' +%Y%m%d%H%M)
  for p in "$PROJECTS"/*/; do
    [ -d "$p" ] && touch -t "$stamp" "$SEEN/$(basename "$p")"
  done
  return 0
}

cmd_list() {
  local cap="${1:-10}"
  local host="${DREAM_HOST:-$(printf '%s' "$PWD" | sed 's|[^a-zA-Z0-9]|-|g')}"
  seed_if_cold

  local dirty=""
  for p in "$PROJECTS"/*/; do
    [ -d "$p" ] || continue
    local slug m
    slug=$(basename "$p")
    # Never consolidate the project this session runs in: its own transcript is
    # still being written, so it would be dirty forever and each dream would
    # mine the previous dream's session as signal.
    [ "$slug" = "$host" ] && continue
    m="$SEEN/$slug"
    if [ ! -e "$m" ] || [ -n "$(find "$p" -maxdepth 1 -name '*.jsonl' -newer "$m" -print -quit)" ]; then
      dirty="$dirty$(find "$p" -maxdepth 1 -name '*.jsonl' -print)
"
    fi
  done

  # Guard the empty case: `xargs ls -t` with no input lists the cwd on some
  # platforms, which would print a bogus "dirty" project.
  printf '%s' "$dirty" | grep -q . || return 0

  printf '%s' "$dirty" | grep . | tr '\n' '\0' | xargs -0 ls -t 2>/dev/null \
    | sed 's|/[^/]*$||' | awk '!s[$0]++' | head -"$cap"
}

cmd_stamp() {
  local dir="${1:?survey.sh stamp <project-dir>}"
  seed_if_cold
  mkdir -p "$SEEN"
  touch "$SEEN/$(basename "$dir")"
}

case "${1:-list}" in
  list)  shift || true; cmd_list "$@" ;;
  stamp) shift; cmd_stamp "$@" ;;
  *)     echo "usage: survey.sh [list [cap] | stamp <project-dir>]" >&2; exit 2 ;;
esac
