#!/usr/bin/env bash
# test-skill-usage.sh — self-check for skill-usage.py. Hand-run:
#   bash test-skill-usage.sh
# Builds a temp fixture; never reads the real ~/.claude and never deletes
# anything. Every path it touches is under $FIX.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
USAGE="$HERE/skill-usage.py"
FIX=$(mktemp -d)
trap 'rm -rf "$FIX"' EXIT

# The fixture: inventory backdated 60 days, transcript activity placed either
# inside or outside a 30-day window, so the window filter is what decides.
python3 - "$FIX" <<'PYEOF'
import json, os, sys, time
from pathlib import Path

fix = Path(sys.argv[1])
home = fix / "claude"
now = time.time()
DAY = 86400
old = now - 60 * DAY


def skill(path, name, declared=None, age=old):
    path.mkdir(parents=True, exist_ok=True)
    md = path / "SKILL.md"
    md.write_text("---\nname: %s\ndescription: fixture\n---\n\nbody\n" % (declared or name))
    os.utime(md, (age, age))


def command(path, age=old):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\ndescription: fixture\n---\n\nbody\n")
    os.utime(path, (age, age))


skill(home / "skills" / "alpha", "alpha")
skill(home / "skills" / "beta", "beta")
# Directory and frontmatter disagree: an invocation of either name is a use.
skill(home / "skills" / "gamma", "gamma", declared="gamma-declared")
skill(home / "skills" / "brandnew", "brandnew", age=now)
skill(home / "skills" / "synced" / "delta", "delta")
command(home / "commands" / "tidy.md")
command(home / "commands" / "dusty.md")
command(home / "commands" / "git" / "sync.md")

plugin = fix / "pl"
(plugin / ".claude-plugin").mkdir(parents=True)
(plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps(
    {"name": "pl", "version": "1.0.0", "skills": "./skills/", "commands": "./commands/"}))
skill(plugin / "skills" / "dream", "dream")
command(plugin / "commands" / "status.md")

(fix / "plugin-list.json").write_text(json.dumps([{
    "id": "pl@fixture", "version": "1.0.0", "scope": "user", "enabled": True,
    "installPath": str(plugin),
    "installedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(old)),
}]))


def stamp(days_ago):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now - days_ago * DAY))


def call(name, days_ago):
    return {"type": "assistant", "timestamp": stamp(days_ago), "message": {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": "t", "name": "Skill", "input": {"skill": name}}]}}


def slash(name, days_ago):
    return {"type": "user", "isMeta": True, "timestamp": stamp(days_ago), "message": {
        "role": "user",
        "content": [{"type": "text",
                     "text": "<command-name>/%s</command-name>" % name}]}}


records = [
    call("alpha", 5),
    call("gamma-declared", 3),
    call("pl:dream", 1),
    call("ghost", 1),
    slash("tidy", 2),
    slash("git:sync", 2),
    # Outside the window. Same transcript, so only the per-record timestamp
    # can exclude it.
    call("beta", 45),
    # The trap: every session carries a listing of every installed skill. A
    # grep for "delta" finds it here; a structural read must not.
    {"type": "attachment", "timestamp": stamp(1),
     "attachment": {"type": "skill_listing",
                    "content": "- delta: Skill for deltas\n- beta: Skill for betas"}},
]

proj = home / "projects" / "-fixture-proj"
proj.mkdir(parents=True)
(proj / "s1.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
PYEOF

export CLEANUP_CLAUDE_HOME="$FIX/claude"
export CLEANUP_PLUGIN_JSON="$FIX/plugin-list.json"

OUT=$(python3 "$USAGE" --days 30 --json) || { echo "FAIL skill-usage.py exited nonzero"; exit 1; }

fail=0
check() { # check <label> <expected> <actual>
  if [ "$2" = "$3" ]; then printf 'ok   %s\n' "$1"
  else printf 'FAIL %s\n  expected: [%s]\n  actual:   [%s]\n' "$1" "$2" "$3"; fail=1; fi
}
field() { # field <jq-ish expression over the report>
  printf '%s' "$OUT" | python3 -c 'import json,sys; r=json.load(sys.stdin); print(eval(sys.argv[1], {"r": r}))' "$1"
}
names() { field "' '.join(sorted(i['token'] for i in r['$1']))"; }

# Sanity guard: if the scan finds nothing at all, every "expected unused"
# check below would pass vacuously.
check "sanity: the window sees the fixture's activity" "6" "$(field "r['invocations_in_window']")"

check "used skills and commands"  "alpha gamma git:sync pl:dream tidy" "$(names used)"
check "unused, across all sources" "beta delta dusty pl:status"        "$(names unused)"
check "installed inside the window is not judged" "brandnew"           "$(names too_new)"
check "an invocation of nothing installed is reported, not silent" "ghost" \
      "$(field "' '.join(r['unmatched'])")"

# The regressions each of these is guarding.
check "a skill named only in a skill_listing is not a use" "synced" \
      "$(field "[i['source'] for i in r['unused'] if i['token']=='delta'][0]")"
check "synced skills carry the do-not-delete note" "True" \
      "$(field "bool([i for i in r['unused'] if i['token']=='delta'][0]['note'])")"
check "frontmatter name counts as a use of the directory" "1" \
      "$(field "[i['uses'] for i in r['used'] if i['token']=='gamma'][0]")"
check "a subfolder command is named the way it is invoked" "1" \
      "$(field "[i['uses'] for i in r['used'] if i['token']=='git:sync'][0]")"

# A wider window has to reach the 45-day-old call, or the window bound is
# being ignored rather than applied.
OUT=$(python3 "$USAGE" --days 90 --json)
check "widening the window reclaims the older use" "alpha beta gamma git:sync pl:dream tidy" \
      "$(names used)"

# --since is the same window, expressed as a date.
OUT=$(python3 "$USAGE" --since "$(python3 -c 'import time; print(time.strftime("%Y-%m-%d", time.gmtime(time.time()-30*86400)))')" --json)
check "--since agrees with the equivalent --days" "alpha gamma git:sync pl:dream tidy" "$(names used)"

# Bad input fails loudly rather than silently scanning a default window.
python3 "$USAGE" --since 'last tuesday' >/dev/null 2>&1
check "an unparseable --since is rejected" "2" "$?"

# An empty home is a clean report, not a crash.
mkdir -p "$FIX/empty"
OUT=$(CLEANUP_CLAUDE_HOME="$FIX/empty" CLEANUP_PLUGIN_JSON="" python3 "$USAGE" --days 30 --json) \
  || { echo "FAIL empty home crashed"; fail=1; OUT='{"unused":[],"used":[]}'; }
check "an empty ~/.claude reports nothing installed" "" "$(names unused)"

[ "$fail" = 0 ] && echo "all checks passed"
exit "$fail"
