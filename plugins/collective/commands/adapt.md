---
description: Adapt the collective's memories into your own, choosing what you take
---

Nothing is ever injected into your memory directory. This command is the only way the collective's memories get there, and what lands is yours — a normal memory file your next dream can merge, delete or rewrite like any other.

1. List what is new or changed for you:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collective.py" adapt
   ```

   The first line is `memory-dir<TAB>path` — your memory directory, as the script computes it. Use that path in step 3; never derive it yourself from the cwd. Every line after it is `new|changed<TAB>name<TAB>path<TAB>description`. No lines after the first means you are up to date — say so and stop.

2. Show the user the list — `new` and `changed` marked, one line each with its description — and ask which to take. Offer all, none, or a subset. Never adapt without asking; taking a teammate's memory is a decision about what this project's Claude believes.

3. For each memory the user chose, ask the script for the file as it should land:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collective.py" adapt --take <name>
   ```

   It strips the team's `sharedBy` and `promotedAt` — provenance for the shared corpus, meaningless once the memory is yours — and records a `pulledFrom` line naming the team memory it came from. Write that output verbatim into the `memory-dir` from step 1 as `<name>.md`, with default permissions, no `team-` prefix, nothing read-only. A file /productivity:dream cannot rewrite is a file that breaks consolidation.

   Do not hand-edit the frontmatter. `pulledFrom` is what lets a later assimilation know this memory extends the team's rather than duplicating it, and it has to survive dream merging and renaming the file.

   If a memory of that name already exists locally, show the user both and let them decide: replace, merge by hand, or skip.

4. Add one line per adapted memory to the `MEMORY.md` in that same directory, in the same format as the entries already there — `- [name](name.md) — description`. Leave the rest of the file alone.

5. Record what was taken so it stops being listed:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collective.py" adapt --mark <name> [<name>...]
   ```

   Mark only the ones actually written. A memory the user skipped should come back next time.
