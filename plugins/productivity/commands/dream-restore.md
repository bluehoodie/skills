---
name: dream-restore
description: Undo a dream — revert one project's memory to before its last consolidation
allowed-tools: Bash, Read
---

Each project's memory directory is its own git repository, and each dream is one
commit. Undoing a dream is a `git revert` — the work is finding the right
repository among dozens of slugs.

1. List the most recent dream commits across every memory repository:

```bash
for m in "$HOME"/.claude/projects/*/memory; do
  [ -d "$m/.git" ] || continue
  git -C "$m" log -3 --grep='^dream:' --format='%h  %ad  %s' --date=short 2>/dev/null | while read -r line; do
    printf '%-45s %s\n' "$(basename "$(dirname "$m")")" "$line"
  done
done
```

Three passes are listed per project — if the memory was lost more than one dream
ago, the commit you want may be the second or third.

Only consolidation passes are listed. The initial `memory: baseline` commit is
deliberately excluded — it holds your memories as they were before dream ever
ran, and reverting it would delete them.

2. Show that list to the user and ask which project, and which pass, to undo. Do
   not guess, and do not revert more than one without being asked. Each row
   carries its own project slug — use the slug and the SHA **from the same
   row**. Do not mix a SHA from one row with the slug from another.

Each step below runs in its own shell — substitute the real slug and SHA into
every command rather than setting a variable, because variables do not carry
between steps.

3. Check the working tree is clean. Only dreams commit here, so uncommitted
   changes are normal and they block a revert.

```bash
git -C "$HOME/.claude/projects/<slug>/memory" status --porcelain
```

If that prints anything, those are memory edits made since the last dream.
Commit them first so they are not lost, then continue:

```bash
git -C "$HOME/.claude/projects/<slug>/memory" add -A -- .
git -C "$HOME/.claude/projects/<slug>/memory" \
  -c user.name=dream -c user.email=dream@localhost commit -qm "save memory edits before restore"
```

4. Revert it. `git revert` creates a commit, so it needs the same identity flags
   the dream used — a machine with no global git config fails otherwise, which is
   the worst possible moment for it. There is no `-q` flag on `git revert`.

```bash
git -C "$HOME/.claude/projects/<slug>/memory" \
  -c user.name=dream -c user.email=dream@localhost revert --no-edit <sha>
```

Check the exit status before continuing. If the revert reports a conflict, it
has created no commit and left the repository mid-revert — do not proceed to
step 5. Abort cleanly:

```bash
git -C "$HOME/.claude/projects/<slug>/memory" revert --abort
```

A conflict means the memory changed again after the dream you are undoing. Tell
the user that, show them `git -C "$HOME/.claude/projects/<slug>/memory" log --oneline -5`,
and ask which state they actually want before trying anything else. Never
resolve a memory conflict on their behalf.

5. Confirm what came back:

```bash
git -C "$HOME/.claude/projects/<slug>/memory" log --oneline -3
ls "$HOME/.claude/projects/<slug>/memory"
```

This restores that project's memory to its state before that dream, and does not
touch any other project. If the user wants the dream re-run afterwards, delete
that project's marker: `rm "$HOME/.claude/dream/seen/<slug>"`.
