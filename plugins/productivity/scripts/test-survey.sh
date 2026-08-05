#!/usr/bin/env bash
# test-survey.sh — self-check for survey.sh. Hand-run: bash test-survey.sh
# Uses a temp fixture; never touches real projects, markers or memory.
set -u

SURVEY="$(cd "$(dirname "$0")" && pwd)/survey.sh"
FIX=$(mktemp -d)
trap 'rm -rf "$FIX"' EXIT

export DREAM_PROJECTS="$FIX/projects"
export DREAM_SEEN="$FIX/seen"
export DREAM_HOST="proj-HOST"

mkdir -p "$DREAM_PROJECTS"/proj-{A,B,C,HOST} "$DREAM_SEEN"
touch -t 202608040900 "$DREAM_PROJECTS/proj-A/s.jsonl"
touch -t 202608030900 "$DREAM_PROJECTS/proj-B/s.jsonl"
touch -t 202608020900 "$DREAM_PROJECTS/proj-C/s.jsonl"
touch -t 202608040901 "$DREAM_PROJECTS/proj-HOST/s.jsonl"
for p in "$DREAM_PROJECTS"/*/; do touch -t 202607280000 "$DREAM_SEEN/$(basename "$p")"; done

fail=0
check() { # check <label> <expected> <actual>
  if [ "$2" = "$3" ]; then printf 'ok   %s\n' "$1"
  else printf 'FAIL %s\n  expected: [%s]\n  actual:   [%s]\n' "$1" "$2" "$3"; fail=1; fi
}
slugs() { sed 's|.*/||' | tr '\n' ' ' | sed 's/ $//'; }

# Sanity guard: the fixture guarantees three dirty projects and nothing has
# been stamped yet. If survey.sh is totally broken (returns nothing at all),
# this fails loudly instead of letting the later "expect empty" checks
# (pass 3, host-exclusion) pass vacuously.
check "sanity: fixture starts with all three projects dirty" "proj-A proj-B proj-C" "$(bash "$SURVEY" list 10 | slugs)"

# Pass 1: cap of 2 takes the two most recently active; host is excluded.
p1=$(bash "$SURVEY" list 2 | slugs)
check "pass 1 dispatches the 2 newest, excludes host" "proj-A proj-B" "$p1"

for s in $p1; do bash "$SURVEY" stamp "$s"; done

# Pass 2: the capped-out project must reappear. This is the starvation
# regression — it fails against a single shared watermark.
p2_raw=$(bash "$SURVEY" list 2)
p2=$(printf '%s\n' "$p2_raw" | slugs)
check "pass 2 picks up the capped-out project" "proj-C" "$p2"

# Exercise the documented calling convention here: stamp gets the absolute
# path list actually emits, not a bare slug — this is what Task 2 passes.
while IFS= read -r path; do [ -n "$path" ] && bash "$SURVEY" stamp "$path"; done <<< "$p2_raw"

# Pass 3: nothing left.
p3=$(bash "$SURVEY" list 2 | slugs)
check "pass 3 converges to empty" "" "$p3"

# A project with no marker at all is dirty on sight.
mkdir -p "$DREAM_PROJECTS/proj-NEW"
touch "$DREAM_PROJECTS/proj-NEW/s.jsonl"
check "unmarked project is dirty" "proj-NEW" "$(bash "$SURVEY" list 10 | slugs)"

# The host is never dispatched, even when it is the most recent activity.
touch "$DREAM_PROJECTS/proj-HOST/s.jsonl"
case " $(bash "$SURVEY" list 10 | slugs) " in
  *" proj-HOST "*) printf 'FAIL host slug leaked into the dirty set\n'; fail=1 ;;
  *)               printf 'ok   host stays excluded when most recent\n' ;;
esac

# --- Cold start: seed_if_cold, exercised for the first time via a $DREAM_SEEN
# that does not exist yet. Dates are set decades away from "now" so the
# assertions hold no matter when this test runs.
COLD_PROJECTS="$FIX/cold-projects"
COLD_SEEN="$FIX/cold-seen"
mkdir -p "$COLD_PROJECTS"/proj-OLD "$COLD_PROJECTS"/proj-RECENT "$COLD_PROJECTS"/proj-3d "$COLD_PROJECTS"/proj-10d
touch -t 200001010000 "$COLD_PROJECTS/proj-OLD/s.jsonl"
touch -t 209901010000 "$COLD_PROJECTS/proj-RECENT/s.jsonl"
# Pin the 7-day seed constant itself: proj-OLD/proj-RECENT sit decades either
# side, so they pass no matter what the seed offset is. These two sit either
# side of the actual 7-day boundary, computed relative to now so the test
# stays stable whenever it runs — this is what catches `-v-7d` silently
# becoming `date` (now).
stamp_3d=$(date -v-3d +%Y%m%d%H%M 2>/dev/null || date -d '3 days ago' +%Y%m%d%H%M)
stamp_10d=$(date -v-10d +%Y%m%d%H%M 2>/dev/null || date -d '10 days ago' +%Y%m%d%H%M)
touch -t "$stamp_3d" "$COLD_PROJECTS/proj-3d/s.jsonl"
touch -t "$stamp_10d" "$COLD_PROJECTS/proj-10d/s.jsonl"

cold=$(DREAM_PROJECTS="$COLD_PROJECTS" DREAM_SEEN="$COLD_SEEN" DREAM_HOST="proj-HOST" bash "$SURVEY" list 10 | slugs)
check "cold start seeds 7 days back: recent + 3-day-old dirty, decades-old + 10-day-old clean" "proj-RECENT proj-3d" "$cold"

if [ -d "$COLD_SEEN" ]; then printf 'ok   cold start creates the seen directory\n'
else printf 'FAIL cold start creates the seen directory\n'; fail=1; fi

seen_files=$(ls "$COLD_SEEN" 2>/dev/null | tr '\n' ' ' | sed 's/ $//')
check "cold start writes one marker per project, not a shared file" "proj-10d proj-3d proj-OLD proj-RECENT" "$seen_files"

# --- Stamp-first: calling `stamp` before any `list` on a cold machine must
# still arm the 7-day seed for every other project, not just create an empty
# $SEEN with a single marker in it (that would permanently disarm seeding,
# since seed_if_cold only fires when $SEEN doesn't exist yet).
STAMP_PROJECTS="$FIX/stamp-cold-projects"
STAMP_SEEN="$FIX/stamp-cold-seen"
mkdir -p "$STAMP_PROJECTS"/proj-X "$STAMP_PROJECTS"/proj-OLD2
touch "$STAMP_PROJECTS/proj-X/s.jsonl"
touch -t 200001010000 "$STAMP_PROJECTS/proj-OLD2/s.jsonl"

DREAM_PROJECTS="$STAMP_PROJECTS" DREAM_SEEN="$STAMP_SEEN" bash "$SURVEY" stamp "$STAMP_PROJECTS/proj-X"
stamp_first=$(DREAM_PROJECTS="$STAMP_PROJECTS" DREAM_SEEN="$STAMP_SEEN" DREAM_HOST="proj-HOST" bash "$SURVEY" list 10 | slugs)
check "stamp-first on a cold machine still arms the 7-day seed" "" "$stamp_first"

[ "$fail" -eq 0 ] && printf '\nall checks passed\n' || printf '\nFAILURES\n'
exit "$fail"
