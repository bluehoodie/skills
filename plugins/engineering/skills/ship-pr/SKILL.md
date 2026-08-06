---
name: ship-pr
description: Use when the user says "ship it", "ship this branch", "open pr and merge", "merge when green", "/ship-pr", or otherwise wants the current branch taken through PR, CI, and merge without babysitting each step. Never auto-merges — merges only after CI is green AND code review has passed.
---

# Ship PR

Take the current branch from local commits to CI-green, reviewed, and merged. Runs the pipeline unattended, but the **merge itself is gated on a passing code review** — never auto-merge.

## Never auto-merge

Do NOT run `gh pr merge --auto` (or arm auto-merge in any form). Auto-merge fires the instant CI goes green, which can land the PR *before* code review finishes — the exact failure this skill guards against. The merge is a deliberate, separate step taken only after BOTH gates are green: CI checks AND code review.

## Flow

1. Confirm clean tree on a feature branch (`git status`). Never run this from `main` — branch first. Dirty tree: commit only if the changes are clearly part of this feature; otherwise stop and report.
2. Push the branch; `gh pr create` targeting the default branch. Title: one line, imperative mood. Check recent merged PRs (`gh pr view <n> --json title,body`) for the repo's body conventions before inventing one.
3. Watch CI: `gh pr checks --watch --fail-fast` in Bash calls capped at 10 min each; one shared ~40 min wall-clock budget for everything after push (reruns, fixes, review, deploy watch included). Do NOT arm auto-merge (see above).
4. On CI trouble:
   - **Failure that matches a known-flaky pattern** (network timeout, unrelated to the diff): `gh run rerun <run-id> --failed`, max 2 attempts; if it still fails, treat as a blocker and report.
   - **Real failure**: read `gh run view <run-id> --log-failed`, fix locally, push, resume watching. Never rerun-until-green on a genuine failure.
   - **Stuck in queued >10 min**: `gh run rerun <run-id>` — full rerun, not `--failed`, so downstream jobs run too. Still stuck on a PR branch: empty commit to retrigger. On `main`: rerun only — NEVER push commits (even empty) directly to main; report if still stuck.
   - Never `--admin`-bypass required checks; never merge over red.
5. **Review gate (must pass before merge).** Once CI is green, obtain a code review and confirm it passes:
   - Run the repo's review path — the `code-review` skill / `/review` on the PR, or a `code-reviewer` agent — over the PR diff. If the repo requires a human/GitHub review approval, wait for it (`gh pr view <n> --json reviewDecision`; APPROVED = pass).
   - Review finds real issues → fix locally, push, re-run CI (step 3) and review. Do NOT merge until review comes back clean.
   - If review cannot be obtained within the budget, STOP and report — do not merge unreviewed.
6. **Merge (only after CI green AND review passed).** Merge with the repo's allowed method (`gh repo view --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed`) — do NOT assume squash; match what recent merged PRs used. Use a one-shot `gh pr merge <n> --squash|--merge|--rebase` (NOT `--auto`).
7. Merged: pull default branch, delete the feature branch locally and remotely.
8. If merging triggers a deploy/main workflow, watch that run too — find it via `gh run list --branch main` and confirm its head SHA matches the merge commit, then `gh run watch`. A failed deploy: report loudly with the failing logs; do not revert main unattended. Done means deployed-checked, not just merged.
9. Report: PR number, merge state, CI/deploy status, review outcome, anything rerun or fixed along the way. If blocked after the budget, stop and report exactly what's blocking and what was tried.

## Done condition

PR shows MERGED **after a passing code review**, local default branch pulled, feature branch deleted, post-merge workflow status checked and reported — or an explicit blocker report.
