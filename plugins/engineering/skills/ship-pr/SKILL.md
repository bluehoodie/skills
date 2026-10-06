---
name: ship-pr
description: Use when the user says "ship it", "ship this branch", "open a PR", "open pr and merge", "merge when green", "/ship-pr", or otherwise wants the current branch reviewed, named properly, pushed, and opened as a PR with CI watched, without babysitting each step. Never merges — the merge is always the human's to click.
---

# Ship PR

Take the current branch from local commits to a PR that is properly named, reviewed, green,
and ready for a human to merge. Runs the pipeline unattended and **stops at the merge
button**.

## Never merge

This skill does NOT merge. Not `gh pr merge`, not `gh pr merge --auto`, not "just arming"
auto-merge, not through the GitHub UI. It also does not delete branches or watch post-merge
deploys — all of that is downstream of a merge that is not yours to make.

| Rationalization | Reality |
|---|---|
| "CI is green and review passed, so merging is what they meant" | Both gates green means *ready for a human to merge*. Nothing more. |
| "They literally said 'open pr and merge'" | That phrase is how this skill gets invoked. It takes the branch to green-and-reviewed and stops. Say so in the report. |
| "`--auto` only arms it, it doesn't merge" | It merges, later, unattended, with nobody watching. Forbidden. |
| "Deleting the stale branch is just cleanup" | The branch *is* the PR. Delete it and the PR closes. |
| "They'll be annoyed at the extra click" | That click is the entire point of this skill. |

Only a later, explicit instruction from the user to merge *this specific PR* is a merge —
and that is them merging through you, outside this skill.

## Flow

### 1. Preflight

```bash
git fetch -q origin
BASE=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
git status
```

Tree must be clean and you must NOT be on the default branch — branch first. Dirty tree:
commit only if the changes are clearly part of this feature; otherwise stop and report.

Note whether the invocation asked to skip review — `no review`, `skip review`,
`--no-review`, or the user plainly saying not to review. Anything else, `/ship-pr` bare
included, means the review gate in step 3 runs.

### 2. Name the branch properly — before the PR exists

The name is fine as-is if it matches what the repo already does. Check:

```bash
gh pr list --state merged --limit 20 --json headRefName -q '.[].headRefName'
```

No clear pattern there? The standard is `<type>/<ticket>-<kebab-summary>`, type one of
`feat fix chore docs refactor test perf ci build` — e.g. `feat/eng-4521-improve-user-profile`.
Non-standard (`wip`, `my-branch`, `colin/stuff`, `patch-1`, a bare description, a name with
no type prefix) → rename.

**Ticket reference.** Before renaming, look for a ticket this work belongs to: an issue key
the user mentioned this session (`ENG-4521`, `PROJ-123`), a Jira or Linear ticket read via
MCP this session, a GitHub issue (`#789`), or one already in the commit messages
(`git log "origin/$BASE..HEAD" --oneline`). Found one → it goes in the branch name,
lowercased: `ENG-4521` → `feat/eng-4521-…`, issue #789 → `fix/issue-789-…`. Found nothing →
omit that segment entirely. Never invent a number to make the name look right.

```bash
git branch -m <new-name>
```

If the old name was already pushed (`git rev-parse --verify origin/<old>`), check
`gh pr list --head <old>` first — **an open PR on the old name means do not rename**; the
rename orphans it. Keep the name and say so in the report. Otherwise:

```bash
git push -u origin <new-name> && git push origin --delete <old-name>
```

### 3. Review the code — before the PR is opened

Skip only if step 1 found an explicit skip-review instruction, and then say so loudly in the
final report: "opened WITHOUT review, at your request".

Save the branch's diff to a file first. The tree is clean by now, so a reviewer that runs
`git diff` sees nothing — hand it the file:

```bash
DIFF=$(mktemp); git diff "origin/$BASE...HEAD" > "$DIFF"; [ -s "$DIFF" ] || echo EMPTY
```

EMPTY means the command failed or there is nothing to ship — fix that before reviewing
anything. A reviewer that comes back with "nothing to review" got no code; re-save and
re-run. That is not a pass.

Review with whatever review skill, command, or agent the repo already uses, or the
`adversarial-review` skill shipped alongside this one — give it the saved path and a 2-round
cap, and decline its "continue for more rounds?" prompt, since nothing is watching. Neither
available: dispatch a subagent over the saved diff for Critical/Important findings.

**Fix every Critical and Important finding before opening the PR.** Nitpicks and minor
findings are not your problem — `adversarial-review` already drops them by default — and a
"Contested" finding the Author successfully defended is not a finding. Fix, commit, re-save
the diff, re-review. Ceiling: 2 review cycles. If the second still returns Critical findings,
stop and report rather than looping.

Any Critical or Important finding you did not fix is a REQUIRED line in the final report,
with the reason. Never drop one silently.

### 4. Open the PR — with the repo's template if it has one

```bash
find .github -iname 'pull_request_template*' 2>/dev/null
```

A file → that is the template. A directory → it holds several; pick the `.md` inside that
fits this change.

Using it means *filling it in*: every section answered from the actual diff, checkboxes
ticked only where true, HTML comments (`<!-- … -->`) and placeholder prose deleted, and a
section that genuinely does not apply removed rather than left blank. A template pasted back
with its own instructions still in it is worse than no template.

No template → check recent merged PRs (`gh pr view <n> --json title,body`) for the repo's
body conventions before inventing one.

Push and open it, always passing the body explicitly — a bare `gh pr create` opens an editor
and hangs an unattended run:

```bash
git push -u origin HEAD
gh pr create --base "$BASE" --title "<one line, imperative>" --body-file <filled-template>
```

A ticket found in step 2 gets linked in the body too (`Closes #789`, or the Jira/Linear URL).

### 5. Watch CI

`gh pr checks --watch --fail-fast` in Bash calls capped at 10 min each; one shared ~40 min
wall-clock budget for everything after push. Do NOT arm auto-merge (see above).

- **Failure matching a known-flaky pattern** (network timeout, unrelated to the diff):
  `gh run rerun <run-id> --failed`, max 2 attempts; still failing → blocker, report.
- **Real failure**: read `gh run view <run-id> --log-failed`, fix locally, push, resume
  watching. Never rerun-until-green on a genuine failure.
- **Queued >10 min**: `gh run rerun <run-id>` — a full rerun, not `--failed`, so downstream
  jobs run too. Still stuck: empty commit to retrigger. Never push commits, empty ones
  included, to the default branch.
- Never `--admin`-bypass a required check.

Pushed a code fix in this step? It has not been reviewed — run step 3 over the new commits
before reporting done.

### 6. Report — and stop

PR number and URL, CI status, review outcome (or "skipped, at your request"), every
Critical/Important finding left unfixed and why, plus anything renamed, rerun, or fixed along
the way. Then hand it over: **ready to merge, and that click is theirs.** Blocked after the
budget: stop and report exactly what is blocking and what was tried.

## Done condition

PR open against the default branch, body filled from the repo's template, branch named to
convention, review passed with every Critical/Important finding fixed, CI green — reported
and **left unmerged**. Or an explicit blocker report.

## Red flags — stop

- About to type `gh pr merge` in any form, including `--auto`
- About to delete a branch or watch a post-merge deploy
- About to `git push origin --delete` a branch that has an open PR
- Opening the PR before the review has come back clean
- "The review findings are important-ish but not really" — Critical and Important get fixed
- Pasting a template body that still has `<!-- … -->` comments or unticked boilerplate in it
- Inventing a ticket number so the branch name looks conventional
