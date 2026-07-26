---
description: Reclaim memories the credential scanner refused, and send the safe ones back through
---

The automatic path handles clean memories on its own. This command exists for the ones it refused: memories the credential scanner flagged, which are never pushed without a person looking at them.

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collective.py" status` to list what is quarantined and why.

2. For each quarantined memory, read the file and decide which case it is:

   - **A real credential.** Say so plainly. Offer to rewrite the memory so it records *that* a secret is involved and where it lives, never its value. The memory is usually more useful that way anyway.
   - **A false positive** — a value that merely looks like a key. Confirm it by reading the surrounding sentence, not by pattern-matching it yourself, then offer to rephrase so the scanner stops tripping.

   Never propose loosening the scanner to clear a blockage. It is deliberately fail-closed, and a pattern removed to unblock one memory stays removed for every future one.

3. Only after the user approves an edit, apply it to the memory file in the project's memory directory. The next assimilation pass rescans it automatically — do not push anything from here.

If nothing is quarantined, say so and stop.
