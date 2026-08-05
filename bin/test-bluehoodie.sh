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
has "manifest records the package version" "\"package\": \"$(node -p "require('$REPO/package.json').version")\"" "$manifest"
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
check "reinstall lands the shipped content" \
  "$(cat "$REPO/plugins/productivity/skills/dream/SKILL.md")" \
  "$(cat "$HOME/.claude/skills/dream/SKILL.md")"

# A path bluehoodie does not own is never clobbered.
mkdir -p "$HOME/.claude/skills/adversarial-review"
echo "mine" > "$HOME/.claude/skills/adversarial-review/SKILL.md"
check "install refuses to clobber a foreign path" "1" \
  "$(bh install engineering/adversarial-review >/dev/null 2>&1; echo $?)"
check "the foreign file is untouched" "mine" "$(cat "$HOME/.claude/skills/adversarial-review/SKILL.md")"
check "--force overrides" "0" \
  "$(bh install engineering/adversarial-review --force >/dev/null 2>&1; echo $?)"
check "--force lands the shipped content, not the mine sentinel" \
  "$(cat "$REPO/plugins/engineering/skills/adversarial-review/SKILL.md")" \
  "$(cat "$HOME/.claude/skills/adversarial-review/SKILL.md")"

# --- Task 2 review fix: a plugin with a same-named skill and command must
# keep both entries owned (manifest keyed by "type:name", not bare name).
# Built under a temp copy of the CLI + a throwaway plugins/ tree, never the
# repo's real plugins/.
FIXROOT=$(mktemp -d)
mkdir -p "$FIXROOT/bin" "$FIXROOT/plugins/fixture/skills/widget" "$FIXROOT/plugins/fixture/commands" \
  "$FIXROOT/plugins/fixture/.claude-plugin"
cp "$CLI" "$FIXROOT/bin/bluehoodie.js"
echo '{"version":"0.0.1"}' > "$FIXROOT/package.json"
echo '{"version":"1.0.0"}' > "$FIXROOT/plugins/fixture/.claude-plugin/plugin.json"
echo 'skill' > "$FIXROOT/plugins/fixture/skills/widget/SKILL.md"
echo 'command' > "$FIXROOT/plugins/fixture/commands/widget.md"

node "$FIXROOT/bin/bluehoodie.js" install fixture >/dev/null
present "same-name skill lands" "$HOME/.claude/skills/widget/SKILL.md"
present "same-name command lands" "$HOME/.claude/commands/widget.md"
fixmanifest=$(cat "$HOME/.claude/bluehoodie/installed.json")
has "manifest keeps the skill entry" '"skill:widget"' "$fixmanifest"
has "manifest keeps the command entry" '"command:widget"' "$fixmanifest"
rm -rf "$FIXROOT"

# --- readManifest resilience (Task 2 review findings 2 & 3)
# A hand-edited manifest missing 'entries' must not crash list or install.
mkdir -p "$HOME/.claude/bluehoodie"
echo '{"package":"0.1.0"}' > "$HOME/.claude/bluehoodie/installed.json"
check "list survives a manifest with no entries key" "0" "$(bh list >/dev/null 2>&1; echo $?)"
check "install survives a manifest with no entries key" "0" \
  "$(bh install productivity/dream --force >/dev/null 2>&1; echo $?)"

# An unparseable manifest is recovered from, not fatal — but it must warn.
echo 'not json' > "$HOME/.claude/bluehoodie/installed.json"
err=$(bh list 2>&1 >/dev/null)
has "corrupt manifest warns on stderr" \
  "bluehoodie: $HOME/.claude/bluehoodie/installed.json is unreadable — treating nothing as installed" "$err"
check "list still exits 0 on a corrupt manifest" "0" "$(bh list >/dev/null 2>&1; echo $?)"

# --- Task 3: support scripts and token rewrite
rm -rf "$HOME/.claude"
bh install productivity >/dev/null

present "scripts land in the per-plugin support dir" \
  "$HOME/.claude/bluehoodie/productivity/scripts/survey.sh"
if [ -x "$HOME/.claude/bluehoodie/productivity/scripts/survey.sh" ]; then
  printf 'ok   survey.sh is executable\n'
else printf 'FAIL survey.sh is not executable\n'; fail=1; fi

# The check that matters most: a plain cp -r passes every "file exists" test
# above and still ships a skill that cannot find its own script.
leaked=$(grep -rl 'CLAUDE_PLUGIN_ROOT' "$HOME/.claude/skills" "$HOME/.claude/commands" 2>/dev/null)
check "no installed file still contains the raw token" "" "$leaked"

# ...and the path it was rewritten to must actually resolve.
rewritten=$(grep -oh '/[^" ]*/scripts/survey.sh' "$HOME/.claude/skills/dream/SKILL.md" | head -1)
present "the rewritten path resolves" "$rewritten"

# The rewrite reaches frontmatter, not just the body.
has "allowed-tools frontmatter is rewritten" "$HOME/.claude/bluehoodie/productivity" \
  "$(head -12 "$HOME/.claude/skills/dream/SKILL.md")"

# A plugin with no scripts/ dir must not grow an empty support dir.
bh install engineering >/dev/null
absent "no scripts dir means no support dir" "$HOME/.claude/bluehoodie/engineering"

# A skill directory's extra files come along, not just its SKILL.md.
present "extra skill files are copied" "$HOME/.claude/skills/adversarial-review/critic-agent.md"

[ "$fail" -eq 0 ] && printf '\nall checks passed\n' || printf '\nFAILURES\n'
exit "$fail"
