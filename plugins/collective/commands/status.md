---
description: Show what the collective holds, what is settling, and what is quarantined
---

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collective.py" status
```

Print the output as-is, then add one line of interpretation:

- **quarantined** entries are memories the credential scanner refused to auto-assimilate. Say what tripped each one and offer to edit the memory so it passes — the scan reruns for free on the next pass once the memory changes.
- **pending** entries are memories written since the last assimilation pass. They are evaluated automatically when the session ends; nothing needs doing.

This command never assimilates anything itself — that happens automatically at SessionEnd. `/collective:reclaim` reviews the quarantined entries above; it doesn't assimilate either.
