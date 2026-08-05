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
# dream/SKILL.md carries ${CLAUDE_PLUGIN_ROOT} and is deliberately rewritten on
# install, so it is not byte-identical to source (see Task 3 below) — assert
# byte-equality on context-tune instead, a same-plugin skill with no token.
check "reinstall lands the shipped content" \
  "$(cat "$REPO/plugins/productivity/skills/context-tune/SKILL.md")" \
  "$(cat "$HOME/.claude/skills/context-tune/SKILL.md")"

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
# above and still ships a skill that cannot find its own script. The needle is
# the exact braced token — the only form the plugin loader substitutes and the
# only one that resolves to empty when nothing substitutes it. Prose that names
# the bare variable or quotes it as a counter-example is harmless and stays.
leaked=$(grep -rlF '${CLAUDE_PLUGIN_ROOT}' "$HOME/.claude/skills" "$HOME/.claude/commands" 2>/dev/null)
check "no installed file still contains the braced token" "" "$leaked"

# ...and the path it was rewritten to must actually resolve.
rewritten=$(grep -oh '/[^" ]*/scripts/survey.sh' "$HOME/.claude/skills/dream/SKILL.md" | head -1)
present "the rewritten path resolves" "$rewritten"

# The rewrite reaches frontmatter, not just the body.
has "allowed-tools frontmatter is rewritten" "$HOME/.claude/bluehoodie/productivity" \
  "$(sed -n '/^---$/,/^---$/p' "$HOME/.claude/skills/dream/SKILL.md")"

# The other half of the invariant: a token-bearing file must NOT install
# byte-identical to source — that would mean the rewrite silently didn't run.
if ! cmp -s "$REPO/plugins/productivity/skills/dream/SKILL.md" "$HOME/.claude/skills/dream/SKILL.md"; then
  printf 'ok   the token-bearing skill is rewritten, not copied verbatim\n'
else printf 'FAIL dream/SKILL.md installed byte-identical — rewrite did not run\n'; fail=1; fi

# A plugin with no scripts/ dir must not grow an empty support dir.
bh install engineering >/dev/null
absent "no scripts dir means no support dir" "$HOME/.claude/bluehoodie/engineering"

# A skill directory's extra files come along, not just its SKILL.md.
present "extra skill files are copied" "$HOME/.claude/skills/adversarial-review/critic-agent.md"

# --- Task 3 review: rewrite must not follow symlinks. statSync throws on a
# dangling one (aborting install mid-way, before writeManifest — an untracked
# partial install) and follows a live one to its target, rewriting a file
# OUTSIDE $HOME. Built under a temp copy of the CLI + throwaway plugins/ tree,
# same pattern as the same-name fixture above — never touches the repo's real
# plugins/. The symlink target lives in its own tempdir, outside $HOME.
SYMFIXROOT=$(mktemp -d)
SYMOUT=$(mktemp -d)
mkdir -p "$SYMFIXROOT/bin" "$SYMFIXROOT/plugins/fixture/skills/linky" "$SYMFIXROOT/plugins/fixture/.claude-plugin"
cp "$CLI" "$SYMFIXROOT/bin/bluehoodie.js"
echo '{"version":"0.0.1"}' > "$SYMFIXROOT/package.json"
echo '{"version":"1.0.0"}' > "$SYMFIXROOT/plugins/fixture/.claude-plugin/plugin.json"
echo 'skill' > "$SYMFIXROOT/plugins/fixture/skills/linky/SKILL.md"
# Named so the live link sorts and is processed before the dangling one: a
# buggy statSync would rewrite-through the live link first (proving that
# failure mode on its own) before the dangling link's ENOENT aborts the run —
# rather than the dangling link masking the live one by crashing first.
printf 'external content, token intact: ${CLAUDE_PLUGIN_ROOT}\n' > "$SYMOUT/external.md"
ln -s "$SYMOUT/external.md" "$SYMFIXROOT/plugins/fixture/skills/linky/a-live.md"
ln -s "$SYMFIXROOT/nonexistent-target.md" "$SYMFIXROOT/plugins/fixture/skills/linky/z-dangling.md"
symbefore=$(cat "$SYMOUT/external.md")

check "install survives a dangling and a live symlink" "0" \
  "$(node "$SYMFIXROOT/bin/bluehoodie.js" install fixture >/dev/null 2>&1; echo $?)"
symmanifest=$(cat "$HOME/.claude/bluehoodie/installed.json")
has "the manifest is still written past the symlinked skill" '"skill:linky"' "$symmanifest"
check "the out-of-tree symlink target is untouched" "$symbefore" "$(cat "$SYMOUT/external.md")"
rm -rf "$SYMFIXROOT" "$SYMOUT"

# --- Task 4: remove
rm -rf "$HOME/.claude"
bh install productivity >/dev/null

out=$(bh remove productivity/dream)
absent "remove deletes the skill" "$HOME/.claude/skills/dream"
has "remove prints the path it deleted" "$HOME/.claude/skills/dream" "$out"
present "remove leaves the plugin's other skills alone" "$HOME/.claude/skills/context-tune/SKILL.md"
present "the support dir survives while siblings remain" \
  "$HOME/.claude/bluehoodie/productivity/scripts/survey.sh"

bh remove productivity >/dev/null
absent "remove <plugin> takes the commands" "$HOME/.claude/commands/dream-status.md"
absent "remove <plugin> takes the last skill" "$HOME/.claude/skills/context-tune"
absent "the support dir goes with the last entry" "$HOME/.claude/bluehoodie/productivity"
check "the manifest is empty afterwards" "0" \
  "$(node -p "Object.keys(require('$HOME/.claude/bluehoodie/installed.json').entries).length")"

# The rule that protects user files: a path bluehoodie did not install is never
# deleted, however much its name looks like one of ours.
mkdir -p "$HOME/.claude/skills/dream"
echo "not ours" > "$HOME/.claude/skills/dream/SKILL.md"
unmanagederr=$(bh remove productivity/dream 2>&1 >/dev/null)
check "remove refuses an unmanaged path" "1" "$(bh remove productivity/dream >/dev/null 2>&1; echo $?)"
has "the refusal names the unmanaged spec, not just any exit 1" \
  "bluehoodie: nothing installed by bluehoodie matches productivity/dream" "$unmanagederr"
check "the unmanaged file survives" "not ours" "$(cat "$HOME/.claude/skills/dream/SKILL.md")"

# --- Task 4 review: the manifest, not the shipped tree, is the source of what
# gets deleted. A skill later renamed or dropped from a release must still be
# removable, and its manifest entry must not permanently pin the plugin's
# support dir. Built under its own throwaway CLI + plugins/ tree, same
# pattern as the symlink fixture above — never touches the repo's real
# plugins/.
rm -rf "$HOME/.claude"
ORPHANROOT=$(mktemp -d)
mkdir -p "$ORPHANROOT/bin" "$ORPHANROOT/plugins/orphan/skills/gone" \
  "$ORPHANROOT/plugins/orphan/scripts" "$ORPHANROOT/plugins/orphan/.claude-plugin"
cp "$CLI" "$ORPHANROOT/bin/bluehoodie.js"
echo '{"version":"0.0.1"}' > "$ORPHANROOT/package.json"
echo '{"version":"1.0.0"}' > "$ORPHANROOT/plugins/orphan/.claude-plugin/plugin.json"
echo 'skill' > "$ORPHANROOT/plugins/orphan/skills/gone/SKILL.md"
echo 'note' > "$ORPHANROOT/plugins/orphan/scripts/note.txt"

node "$ORPHANROOT/bin/bluehoodie.js" install orphan >/dev/null
present "orphan fixture installed before the shipped skill is dropped" "$HOME/.claude/skills/gone/SKILL.md"

# Simulate a later release that renames or drops the skill from the shipped tree.
rm -rf "$ORPHANROOT/plugins/orphan/skills/gone"

check "remove of an orphaned entry exits clean" "0" \
  "$(node "$ORPHANROOT/bin/bluehoodie.js" remove orphan >/dev/null 2>&1; echo $?)"
absent "the orphaned skill is deleted despite being gone from the shipped tree" "$HOME/.claude/skills/gone"
absent "the support dir goes with the orphaned entry" "$HOME/.claude/bluehoodie/orphan"
check "the orphaned manifest entry is gone" "false" \
  "$(node -p "'skill:gone' in require('$HOME/.claude/bluehoodie/installed.json').entries" 2>/dev/null || echo false)"
rm -rf "$ORPHANROOT"

# The protection the manifest-as-source-of-paths design now needs: a crafted
# manifest key must never let rmSync escape ~/.claude. One entry uses "../"
# traversal, one uses an absolute-looking name; both are aimed at the same
# real file living outside the temp $HOME.
rm -rf "$HOME/.claude"
VICTIM=$(mktemp -d)
echo "precious external content" > "$VICTIM/secret.txt"
victimbefore=$(cat "$VICTIM/secret.txt")
RELPATH="${VICTIM#/}/secret.txt"
UPDOTS="../../../../../../../../../../../../../../../../../../../../"

mkdir -p "$HOME/.claude/bluehoodie"
node -e '
const fs = require("fs")
const [, manifestPath, trav, abs] = process.argv
const m = { package: "0.0.0", entries: {} }
m.entries["skill:" + trav] = { type: "skill", plugin: "escape", version: "1.0.0" }
m.entries["skill:" + abs] = { type: "skill", plugin: "escape", version: "1.0.0" }
fs.writeFileSync(manifestPath, JSON.stringify(m, null, 2) + "\n")
' "$HOME/.claude/bluehoodie/installed.json" "${UPDOTS}${RELPATH}" "$VICTIM/secret.txt"

ESCROOT=$(mktemp -d)
mkdir -p "$ESCROOT/bin" "$ESCROOT/plugins/escape"
cp "$CLI" "$ESCROOT/bin/bluehoodie.js"
echo '{"version":"0.0.1"}' > "$ESCROOT/package.json"

escout=$(node "$ESCROOT/bin/bluehoodie.js" remove escape 2>&1)
escstatus=$?
check "a crafted manifest entry does not exit 0" "1" "$escstatus"
has "the refusal names the containment rule" "refusing to remove" "$escout"
check "the outside victim survives the traversal attempt" "$victimbefore" "$(cat "$VICTIM/secret.txt")"
rm -rf "$ESCROOT" "$VICTIM"

[ "$fail" -eq 0 ] && printf '\nall checks passed\n' || printf '\nFAILURES\n'
exit "$fail"
