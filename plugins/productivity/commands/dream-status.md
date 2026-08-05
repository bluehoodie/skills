---
name: dream-status
description: Show which projects need a dream, and the state of the memory stores
allowed-tools: Bash
---

```bash
SURVEY="${CLAUDE_PLUGIN_ROOT}/scripts/survey.sh"
SEEN="$HOME/.claude/dream/seen"

echo "Dream — machine-wide memory consolidation"
if [ ! -d "$SEEN" ]; then
  echo "  never run. The first pass will cover the last 7 days."
else
  echo "  markers      $(ls -1 "$SEEN" 2>/dev/null | wc -l | tr -d ' ') projects tracked"
  LATEST=$(ls -t "$SEEN" 2>/dev/null | head -1)
  [ -n "$LATEST" ] && echo "  last stamped $LATEST at $(date -r "$SEEN/$LATEST" '+%Y-%m-%d %H:%M' 2>/dev/null)"
fi

echo "  dirty now:"
DIRTY=$(DREAM_SEEN="$SEEN" bash "$SURVEY" list 100)
if [ -z "$DIRTY" ]; then
  echo "    none — memory is up to date"
else
  echo "$DIRTY" | while read -r p; do
    n=$(ls -1 "$p/memory"/*.md 2>/dev/null | wc -l | tr -d ' ')
    echo "    $(basename "$p")  ($n memories)"
  done
fi

echo
echo "  re-dream one project:  rm $SEEN/<slug>"
echo "  re-dream everything:   rm -rf $SEEN"
```

Show the output to the user verbatim. Do not summarise it, and do not offer to run
a dream unless asked.

This command does not consolidate anything and never touches a memory directory.
It is not, however, strictly side-effect free: on a machine that has never dreamed,
the survey initialises `~/.claude/dream/seen/` and seeds a marker per project dated
7 days back. That is what makes "dirty" mean "active in the last week" rather than
"every project ever opened", so a status query on a cold machine reports the same
set a dream would — which is the useful answer. It happens once; every later run
only reads. Say so if the user asks why markers appeared.
