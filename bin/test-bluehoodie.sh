#!/usr/bin/env bash
# test-bluehoodie.sh — self-check for bluehoodie.js. Hand-run: bash test-bluehoodie.sh
# Runs the real CLI against a throwaway $HOME; never touches your real ~/.claude.
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$REPO/bin/bluehoodie.js"
FIX=$(mktemp -d)
trap 'rm -rf "$FIX"' EXIT

export HOME="$FIX/home"
mkdir -p "$HOME"

bh() { node "$CLI" "$@"; }

fail=0
check() { # check <label> <expected> <actual>
  if [ "$2" = "$3" ]; then printf 'ok   %s\n' "$1"
  else printf 'FAIL %s\n  expected: [%s]\n  actual:   [%s]\n' "$1" "$2" "$3"; fail=1; fi
}
present() { # present <label> <path>
  if [ -e "$2" ]; then printf 'ok   %s\n' "$1"
  else printf 'FAIL %s\n  missing: %s\n' "$1" "$2"; fail=1; fi
}
absent() { # absent <label> <path>
  if [ ! -e "$2" ]; then printf 'ok   %s\n' "$1"
  else printf 'FAIL %s\n  still present: %s\n' "$1" "$2"; fail=1; fi
}
has() { # has <label> <needle> <haystack>
  case "$3" in *"$2"*) printf 'ok   %s\n' "$1" ;;
    *) printf 'FAIL %s\n  no [%s] in:\n%s\n' "$1" "$2" "$3"; fail=1 ;; esac
}

# --- Task 1: discovery and list
out=$(bh list)
check "list exits clean" "0" "$(bh list >/dev/null 2>&1; echo $?)"
has "list names the dream skill" "productivity/dream" "$out"
has "list names the dream-status command" "productivity/dream-status" "$out"
has "list names the adversarial-review skill" "engineering/adversarial-review" "$out"
has "list reports the plugin version" "productivity $(node -p "require('$REPO/plugins/productivity/.claude-plugin/plugin.json').version")" "$out"

# skills and commands print with their type marker
has "list marks types" "(skill)" "$out"
has "list marks command types" "(command)" "$out"

# list must not crash or write anything when nothing is installed yet.
absent "list writes no manifest" "$HOME/.claude/bluehoodie/installed.json"

# resolve()'s unknown-plugin/unknown-skill exits move here once Task 2 adds
# install() and resolve() is actually reachable; asserted against stderr then.

[ "$fail" -eq 0 ] && printf '\nall checks passed\n' || printf '\nFAILURES\n'
exit "$fail"
