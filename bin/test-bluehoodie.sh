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

err=$(bh install nope/thing 2>&1 >/dev/null)
has "unknown plugin names the plugin" "bluehoodie: unknown plugin: nope" "$err"
err=$(bh install productivity/nope 2>&1 >/dev/null)
has "unknown skill names the target" "bluehoodie: unknown skill or command: productivity/nope" "$err"

# --- Task 2: install
out=$(bh install productivity/dream)
present "install lands the dream skill" "$HOME/.claude/skills/dream/SKILL.md"
has "install prints the absolute path it wrote" "$HOME/.claude/skills/dream" "$out"
present "install writes the manifest" "$HOME/.claude/bluehoodie/installed.json"

manifest=$(cat "$HOME/.claude/bluehoodie/installed.json")
has "manifest records the plugin" '"plugin": "productivity"' "$manifest"
has "manifest records the type" '"type": "skill"' "$manifest"
has "manifest records the package version" '"package"' "$manifest"
# The recorded version is the PLUGIN's, not the package's — they differ, so a
# manifest that stored the package version by mistake fails here.
has "manifest records the plugin version" "\"version\": \"$(node -p "require('$REPO/plugins/productivity/.claude-plugin/plugin.json').version")\"" "$manifest"

has "list marks it installed" "[installed]" "$(bh list)"

# Whole-plugin install picks up commands as flat .md files.
bh install productivity >/dev/null
present "install <plugin> lands dream-status" "$HOME/.claude/commands/dream-status.md"
present "install <plugin> lands dream-restore" "$HOME/.claude/commands/dream-restore.md"
present "install <plugin> lands context-tune" "$HOME/.claude/skills/context-tune/SKILL.md"

# Reinstalling something bluehoodie owns is an upgrade, not an error.
check "reinstall succeeds" "0" "$(bh install productivity/dream >/dev/null 2>&1; echo $?)"

# A path bluehoodie does not own is never clobbered.
mkdir -p "$HOME/.claude/skills/adversarial-review"
echo "mine" > "$HOME/.claude/skills/adversarial-review/SKILL.md"
check "install refuses to clobber a foreign path" "1" \
  "$(bh install engineering/adversarial-review >/dev/null 2>&1; echo $?)"
check "the foreign file is untouched" "mine" "$(cat "$HOME/.claude/skills/adversarial-review/SKILL.md")"
check "--force overrides" "0" \
  "$(bh install engineering/adversarial-review --force >/dev/null 2>&1; echo $?)"

[ "$fail" -eq 0 ] && printf '\nall checks passed\n' || printf '\nFAILURES\n'
exit "$fail"
