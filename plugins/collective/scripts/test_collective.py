#!/usr/bin/env python3
"""Self-check for collective.py. Run: python3 scripts/test_collective.py

Every test runs against a sandbox $HOME and a throwaway git repo, so the suite
never touches real memories, a real remote, or the real `claude` binary.

The scan tests carry the most weight here. Everything else in this plugin is a
file copy; scan is the only thing standing between a memory that mentions an API
key and a public pull request. A false positive costs a manual review. A false
negative is a leaked credential, so the blocker cases are enumerated one per
line rather than folded into a loop — a missing case should be visible as a
missing line.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collective as ds

FAILED = 0


def check(label, expected, actual):
    global FAILED
    if actual == expected:
        print(f"ok   — {label}")
    else:
        print(f"FAIL — {label} (expected {expected!r}, got {actual!r})")
        FAILED = 1


def blocks(label, text):
    check(f"blocks {label}", True, bool(ds.scan(text)))


def allows(label, text):
    hits = ds.scan(text)
    check(f"allows {label}", [], hits)


# ---------------------------------------------------------------- scan: block

blocks("an Anthropic key", "set ANTHROPIC_API_KEY to sk-ant-api03-JJx8s0vQmT4hLpZ2nR7wYcE1dF")
blocks("an OpenAI key", "the key is sk-proj-8s0vQmT4hLpZ2nR7wYcE1dFbG3kM9pXu")
blocks("a GitHub PAT", "auth with ghp_16C7e42F292c6912E7710c838347Ae178B4a")
blocks("a fine-grained GitHub PAT", "github_pat_11ABCDEFG0aBcDeFgHiJkL_mNoPqRsTuVwXyZ012345")
blocks("an AWS access key id", "the runner uses AKIAIOSFODNN7EXAMPLE for S3")
# The token literal is split so GitHub push protection doesn't flag this fixture.
blocks("a Slack token", "webhook auth xoxb-" + "2401234567-2401234567890-AbCdEfGhIjKlMnOpQrStUvWx")
blocks("a private key block", "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNza\n")
blocks("a JWT", "bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N")
blocks("a KEY=secret assignment", 'run with DB_PASSWORD="hunter2-correct-horse-battery"')
blocks("a bare high-entropy token", "the shared secret is Xk7pQ2mZ9vLbN4tR8wYcE1dFgH3jK5sA6uI0oP")
blocks("a real password in a connection string",
       "connect with postgresql://whales:s3cret-horse-battery@db:5433/whales")

# ------------------------------------------------------------- scan: allow
#
# These are the shapes that appear constantly in real memories. If any of them
# blocks, auto-assimilate stops firing and the whole plugin degrades into a manual
# queue nobody reads.

allows("ordinary prose", "The receiver writes to Postgres before the sidecar reads it.")
allows("an env var name with no value", "check .env for WHALE_SIM_RESET before restarting")
allows("a placeholder value", 'set API_KEY="your-key-here" in the template')
allows("a boolean assignment", "WHALE_SIM_RESET=true wipes the sim database on startup")
allows("a port assignment", "RECEIVER_PORT=8080 in deploy/env/staging.env")
allows("a commit sha", "regressed in 4f9d2c1a8b3e5f70d6c4a2b9e8f1037c5d2e4a6b")
allows("a wikilink", "see [[project-sidecar-usdc-decimal-precision]] for the outage")
allows("a home path", "the vault lives at /Users/alice/vaults/notes")
allows("an internal ip", "the receiver is at 10.0.1.5:8080")
allows("a mdns hostname", "deploy target is pi-one.local")
allows("a uuid", "projectId 5bdba730-726c-4ed9-a015-53235d4584d6")
# Real memories document connection strings with the password stood in for.
# Blocking those blocked a genuine memory on the first end-to-end run.
allows("a placeholder in a connection string",
       "connect with postgresql://whales:PASS@localhost:5433/whales")
allows("a masked password", "postgresql://whales:****@localhost:5433/whales")

# --------------------------------------------------------------- redact
#
# Home paths, private IPs and mDNS names are not secrets — they are
# deanonymizing and machine-specific. Blocking on them would send nearly every
# memory to manual review, so they are rewritten deterministically instead.
# Deterministic beats an LLM rewrite here: the substitution is mechanical and a
# model that paraphrases the surrounding sentence changes the memory's meaning.

body, notes = ds.redact("the vault lives at /Users/alice/vaults/notes")
check("redacts a macOS home path", "the vault lives at ~/vaults/notes", body)
check("reports the redaction", True, any("home path" in n for n in notes))

body, _ = ds.redact("logs are under /home/bob/srv/receiver")
check("redacts a linux home path", "logs are under ~/srv/receiver", body)

body, _ = ds.redact("the receiver is at 10.0.1.5:8080 and 192.168.1.22")
check("redacts private ipv4", "the receiver is at <host>:8080 and <host>", body)

body, _ = ds.redact("deploy target is pi-one.local")
check("redacts mdns hostnames", "deploy target is <host>", body)

body, _ = ds.redact("the public resolver is 8.8.8.8")
check("leaves public ipv4 alone", "the public resolver is 8.8.8.8", body)

body, _ = ds.redact("nothing to see here")
check("leaves clean text byte-identical", "nothing to see here", body)

# A redacted body must still be clean. If redaction introduced something the
# scanner would have blocked, the order of the two gates is wrong.
dirty = "path /Users/alice/x, host pi.local, ip 10.0.0.1"
check("redacted output passes the scanner", [], ds.scan(ds.redact(dirty)[0]))


# ---------------------------------------------------------------- sandbox

class Sandbox:
    """A fake $HOME with one git repo and one project memory directory."""

    def __init__(self, team=True, git=True):
        self.home = Path(tempfile.mkdtemp())
        self.work = self.home / "work"
        self.work.mkdir()
        self.slug = str(self.work).replace("/", "-")
        self.project = self.home / ".claude" / "projects" / self.slug
        self.memory = self.project / "memory"
        self.memory.mkdir(parents=True)
        if git:
            self.run_git("init", "-q", "-b", "main")
        self.team = self.work / ".collective-memory"
        if team:
            self.team.mkdir(parents=True)
        os.environ["HOME"] = str(self.home)

    def run_git(self, *args):
        subprocess.run(["git", "-C", str(self.work), *args],
                       capture_output=True, check=False)

    def shared(self, name, description="a team fact", body="Body."):
        (self.team / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n"
            f"metadata:\n  type: project\n---\n\n{body}\n")

    def local(self, name, body="Mine.", type="project"):
        (self.memory / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: local\n"
            f"metadata:\n  type: {type}\n---\n\n{body}\n")

    def untyped(self, name, body="Mine."):
        (self.memory / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: local\n---\n\n{body}\n")

    def settle(self):
        """Back-date every memory past the settle window, as leaving them would."""
        old = time.time() - ds.SETTLE - 60
        for f in self.memory.glob("*.md"):
            os.utime(f, (old, old))

    def origin(self):
        """Give the repo a real bare remote, so open_pr gets as far as a branch."""
        self.run_git("config", "user.email", "dev@example.com")
        self.run_git("config", "user.name", "dev")
        self.run_git("commit", "-q", "--allow-empty", "-m", "init")
        bare = self.home / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)],
                       capture_output=True)
        self.run_git("remote", "add", "origin", str(bare))
        self.run_git("push", "-q", "origin", "main")
        self.run_git("remote", "set-head", "origin", "main")

    def index(self):
        f = self.memory / "MEMORY.md"
        return f.read_text() if f.exists() else ""


def branch_of(result):
    """The branch name out of open_pr's dry-run line."""
    return result.split("branch ")[-1].split(" ")[0]


def tree_of(sandbox, branch):
    return ds.run(["git", "-C", str(sandbox.work), "ls-tree", "-r", "--name-only",
                   branch]) or ""


def blob_of(sandbox, branch, path):
    return ds.run(["git", "-C", str(sandbox.work), "show", f"{branch}:{path}"]) or ""


def capture(fn, *args):
    """What fn printed. status() reports through stdout, so that is what to assert."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


# ---------------------------------------------------- assimilation candidates
#
# Two gates. The settle window comes first — a memory still being revised is one
# session's impression, not something to hand a teammate — and the manifest is
# the queue behind it, admitting each memory once per content hash.

s = Sandbox()
s.local("project-a")
s.local("project-b")
# Written before the assertion below or it excludes nothing: a real memory
# directory always has an index.
(s.memory / "MEMORY.md").write_text("# Memory\n")
s.settle()
check("every settled memory is a candidate", 2, len(ds.candidates(s.project)))
check("MEMORY.md is never a candidate", True,
      all(c.name != "MEMORY.md" for c in ds.candidates(s.project)))

ds.mark_considered(s.project, ds.candidates(s.project))
check("considered memories stop being candidates", 0, len(ds.candidates(s.project)))

s.local("project-a", body="Revised with a new detail.")
s.settle()
check("an edited memory becomes a candidate again", 1, len(ds.candidates(s.project)))

# The settle window. A memory nobody has touched for a day survived past the
# session that produced it; one written moments ago has not.
s = Sandbox()
s.local("project-old")
s.settle()
s.local("project-new")
names = [c.stem for c in ds.candidates(s.project)]
check("a memory left alone is assimilable", True, "project-old" in names)
check("a memory written moments ago is still settling", False, "project-new" in names)

# Rewriting restarts the clock, which is the whole point: a memory being revised
# is a draft, whether the reviser is the user, auto-memory or a consolidation.
s = Sandbox()
s.local("project-a")
s.settle()
check("a settled memory is a candidate", 1, len(ds.candidates(s.project)))
s.local("project-a", body="Revised again.")
check("editing it restarts the clock", 0, len(ds.candidates(s.project)))

# collective and dream are separate plugins. Neither requires the other, and
# nothing here may consult the other's state: a sandbox with no dream plugin,
# no state directory and no lock still assimilates.
s = Sandbox()
s.local("project-a")
s.settle()
check("assimilation needs no dream plugin installed", 1, len(ds.candidates(s.project)))
check("and reads nothing the dream plugin owns", False,
      (s.home / ".claude" / "dream-plugin-state").exists())


# ------------------------------------------------------- individual memories
#
# The gate the credential scanner is to secrets, for the other kind of leak. A
# memory's `type` already records whether it is about its author, so that is read
# rather than inferred: `user` is who they are, `feedback` is how they like to be
# worked with, and neither is the team's business. Getting this wrong is
# unrecoverable in a way a missed share is not — the corpus is git history.

check("reads the type out of the metadata block", "user",
      ds.memory_type("---\nname: m\nmetadata:\n  type: user\n---\n\nBody.\n"))
check("a memory with no type has none", None,
      ds.memory_type("---\nname: m\ndescription: d\n---\n\nBody.\n"))
# stamp() writes `node_type: memory` on memories that arrive without frontmatter.
# A regex anchored loosely enough to read that as the type would misclassify them.
check("node_type is not the type", None,
      ds.memory_type("---\nname: m\nmetadata:\n  node_type: memory\n---\n\nBody.\n"))

s = Sandbox()
s.local("project-fact", type="project")
s.local("project-link", type="reference")
s.local("user-role", type="user")
s.local("feedback-rebase", type="feedback")
s.untyped("project-legacy")
s.settle()
names = sorted(c.stem for c in ds.candidates(s.project))
check("a project memory is assimilable", True, "project-fact" in names)
check("a reference memory is assimilable", True, "project-link" in names)
check("a user memory is never assimilable", False, "user-role" in names)
check("a feedback memory is never assimilable", False, "feedback-rebase" in names)
# Deliberate: blocking on a missing field would silently disable assimilation for
# anyone whose memories lack it. The classifier is still the second line here.
check("an untyped memory is left to the classifier", True, "project-legacy" in names)

# The point of doing this deterministically is that the model never sees them.
s = Sandbox()
s.local("user-role", type="user", body="Colin is a staff engineer who prefers rebase.")
s.local("feedback-rebase", type="feedback", body="Always rebase, never merge.")
s.settle()
os.environ["COLLECTIVE_GRAPHIFY"] = "0"
prev = ds.CLAUDE_BIN
ds.CLAUDE_BIN = "/nonexistent-classifier-must-not-run"
check("individual memories never reach the classifier", "nothing new",
      ds.assimilate(s.project, str(s.work)))
ds.CLAUDE_BIN = prev
del os.environ["COLLECTIVE_GRAPHIFY"]

check("status reports what it withheld as individual", True,
      "individual      2" in capture(ds.status, s.project, str(s.work)))


# ---------------------------------------------------------------------- adapt
#
# The read path lists; /collective:adapt writes. Keyed by content digest for the same
# reason the assimilation manifest is: a memory the team edited comes back as
# changed, re-reading the directory changes nothing.

s = Sandbox()
s.shared("project-clob-v2", "CLOB v2 orders need an explicit nonce")
s.shared("project-grafana", "Grafana tenants are separated by org id")
(s.team / "MEMORY.md").write_text("# not a memory\n")
rows = ds.adapt(s.project, str(s.work))
check("every unpulled team memory is listed", 2, len(rows))
check("they are marked new", ["new", "new"], [state for state, _ in rows])
check("the team MEMORY.md is never listed", True, all(f.stem != "MEMORY" for _, f in rows))
check("the description comes along", "CLOB v2 orders need an explicit nonce",
      ds.describe(rows[0][1]))

ds.mark_pulled(s.project, str(s.work), ["project-clob-v2"])
check("a pulled memory drops off the list", ["project-grafana"],
      [f.stem for _, f in ds.adapt(s.project, str(s.work))])

s.shared("project-clob-v2", "CLOB v2 orders need an explicit nonce",
         body="Now with the fee schedule.")
states = {f.stem: state for state, f in ds.adapt(s.project, str(s.work))}
check("a team memory edited since the pull comes back", "changed",
      states.get("project-clob-v2"))
check("one never pulled is still new", "new", states.get("project-grafana"))

s = Sandbox(team=False)
check("adapt no-ops without a collective-memory directory", [], ds.adapt(s.project, str(s.work)))

s = Sandbox(git=False)
s.shared("project-x")
check("adapt no-ops outside a git repo", [], ds.adapt(s.project, str(s.work)))


# --------------------------------------------------------------------- resolve
#
# assimilate gets a transcript_path from the SessionEnd hook; status and adapt are
# run from a slash command and never do. The fallback has to land on the same
# directory Claude Code uses, which dashes EVERY non-alphanumeric character —
# keying on only the slashes sent every command-invoked verb to a state
# directory assimilate had never written.

project, _ = ds.resolve({"cwd": "/Users/x/code/my_app.v2"})
check("the cwd fallback slugifies the way Claude Code does",
      "-Users-x-code-my-app-v2", project.name)


# ----------------------------------------------------------------- assimilate
#
# Everything here is about what assimilate does with a batch it could NOT finish.
# A candidate marked considered never comes back unless its bytes change, and
# assimilate runs detached from a SessionEnd hook, so anything dropped is dropped
# silently and for good.

class FakeClaude:
    """A `claude -p` stand-in.

    assimilate makes two different kinds of model call — classify, over the whole
    batch, and the meaning comparison for a candidate that extends something
    already shared. The real binary tells them apart by the prompt it is handed,
    so the stand-in does too rather than returning one answer to both.
    """

    def __init__(self, verdicts, change=None):
        self.dir = Path(tempfile.mkdtemp())
        self.log = self.dir / "argv"
        binary = self.dir / "claude"
        change = change if change is not None else {"changed": True, "what": "a new fact"}
        # Matched against the whole argv, not $2 — the two calls pass different
        # flags, so the prompt is not at a fixed position.
        binary.write_text(
            "#!/usr/bin/env bash\n"
            # One line per invocation: prompts are multi-line, so newlines are
            # stripped before logging or a single call looks like dozens.
            f'printf "%s " "$@" | tr -d "\\n" >> "{self.log}"\n'
            f'printf "\\n" >> "{self.log}"\n'
            'if [[ "$*" == *"CURRENT:"* ]]; then\n'
            "cat <<'CHANGED'\n" + json.dumps(change) + "\nCHANGED\n"
            "else\n"
            "cat <<'VERDICTS'\n" + json.dumps(verdicts) + "\nVERDICTS\n"
            "fi\n")
        binary.chmod(0o755)
        self.prev = ds.CLAUDE_BIN
        ds.CLAUDE_BIN = str(binary)

    def calls(self):
        """One line per invocation, as the argv the script was handed."""
        return self.log.read_text().splitlines() if self.log.exists() else []

    def restore(self):
        ds.CLAUDE_BIN = self.prev


def verdict(name, body, extends=None):
    return [{"name": name, "shareable": True, "confidence": 0.95,
             "reason": "durable fact about the codebase",
             "extends": extends, "body": body}]


os.environ["COLLECTIVE_GRAPHIFY"] = "0"

# A rate limit, an expired token and a timeout all reach assimilate as an empty
# verdict list. Marking that batch considered would retire it permanently.
s = Sandbox()
s.local("project-a")
s.settle()
prev = ds.CLAUDE_BIN
ds.CLAUDE_BIN = "false"
check("a classifier failure is not a verdict",
      "classifier unavailable — retrying next session", ds.assimilate(s.project, str(s.work)))
check("a memory the classifier never saw is still a candidate",
      1, len(ds.candidates(s.project)))
ds.CLAUDE_BIN = prev

# No origin here, so open_pr fails at the fetch — the same shape as being offline
# when the session ends, which is when this hook runs.
s = Sandbox()
s.local("project-a", body="The receiver writes to Postgres before the sidecar reads it.")
s.settle()
c = FakeClaude(verdict("project-a", "---\nname: project-a\n---\n\nA durable fact.\n"))
check("an assimilation that never reached the remote says so",
      "PR failed — branch left unpushed", ds.assimilate(s.project, str(s.work)))
check("and its memory is still a candidate", 1, len(ds.candidates(s.project)))
c.restore()

# The other half of that rule: an assimilation that did complete must not repeat.
s = Sandbox()
s.local("project-a", body="The receiver writes to Postgres before the sidecar reads it.")
s.settle()
s.origin()
ds.DRY_RUN = True
c = FakeClaude(verdict("project-a", "---\nname: project-a\n---\n\nA durable fact.\n"))
check("a completed assimilation reports the branch", True,
      "(dry run) branch assimilate/" in (ds.assimilate(s.project, str(s.work)) or ""))
check("and its memory stops being a candidate", 0, len(ds.candidates(s.project)))
c.restore()
ds.DRY_RUN = False

# The classifier's own two refusals. Both branches implement the privacy promise
# and neither was covered: a verdict of `shareable: false` and a verdict the model
# is not confident enough about must leave the memory at home.
s = Sandbox()
s.local("project-mine", body="Something the model judges personal.")
s.settle()
c = FakeClaude([{"name": "project-mine", "shareable": False, "confidence": 0.99,
                 "reason": "about the author, not the codebase", "extends": None,
                 "body": "---\nname: project-mine\n---\n\nLeaked.\n"}])
check("a refused memory is not assimilated",
      "1 evaluated, none met the bar, 0 blocked", ds.assimilate(s.project, str(s.work)))
check("and nothing was written to the corpus", [], list(s.team.glob("*.md")))
c.restore()

s = Sandbox()
s.local("project-mine", body="Something the model is unsure about.")
s.settle()
c = FakeClaude([{"name": "project-mine", "shareable": True, "confidence": 0.5,
                 "reason": "might be team knowledge", "extends": None,
                 "body": "---\nname: project-mine\n---\n\nUnsure.\n"}])
check("a verdict below the confidence bar is not assimilated",
      "1 evaluated, none met the bar, 0 blocked", ds.assimilate(s.project, str(s.work)))
c.restore()

# ----------------------------------------------------- meaningful changes
#
# Whether two versions say the same thing is a question about meaning, so a model
# answers it. What is tested here is therefore OUR half — the short-circuit that
# avoids the call, the parsing of the answer, and which way it falls when the
# answer never arrives. The model's judgment is not ours to assert.

same = "The sidecar rounds USDC to 6 decimals before writing to Postgres."

# No model should be consulted to notice that text is identical to itself, so these
# run against a binary that does not exist. If one of them tries to call it, the
# short-circuit is not doing its job and the answer comes back "could not compare".
prev = ds.CLAUDE_BIN
ds.CLAUDE_BIN = "/nonexistent-comparator"
check("identical text needs no model call", (False, None), ds.meaningful(same, same))
check("whitespace needs no model call", (False, None),
      ds.meaningful(same, "The sidecar  rounds USDC to 6 decimals\nbefore writing to Postgres."))
check("case needs no model call", (False, None), ds.meaningful(same, same.lower()))
# And the fail-open direction, which this binary is now demonstrating: a comparison
# that cannot be made must not silently suppress a correction.
check("an unanswerable comparison ships anyway", (True, "could not be compared"),
      ds.meaningful(same, "The sidecar rounds USDC to 8 decimals."))
ds.CLAUDE_BIN = prev

reworded = "USDC is rounded by the sidecar to 6 decimals before it writes to Postgres."
c = FakeClaude([], change={"changed": False, "what": None})
check("a verdict of reword suppresses the update", (False, None), ds.meaningful(same, reworded))
c.restore()

c = FakeClaude([], change={"changed": True, "what": "6 decimals becomes 8"})
check("a verdict of change reports what changed", (True, "6 decimals becomes 8"),
      ds.meaningful(same, "The sidecar rounds USDC to 8 decimals."))
c.restore()

c = FakeClaude([], change="not json at all")
check("an unparseable verdict ships anyway", (True, "could not be compared"),
      ds.meaningful(same, "The sidecar rounds USDC to 8 decimals."))
c.restore()

# The comparison is a narrow, well-scoped question, so it runs on the cheapest
# model that can answer it — and only it does. Classifying team-vs-personal and
# rewriting a memory for a team audience is the harder judgment and stays on
# whatever model the session is already using.
s = Sandbox()
s.shared("project-sidecar", "the sidecar rounds USDC",
         body="The sidecar rounds USDC to 6 decimals before writing to Postgres.")
s.local("project-sidecar",
        body="The sidecar rounds USDC to 8 decimals before writing to Postgres.")
s.origin()
s.settle()
ds.DRY_RUN = True
c = FakeClaude(verdict("project-sidecar",
                       "---\nname: project-sidecar\n---\n\n"
                       "The sidecar rounds USDC to 8 decimals before writing to Postgres.\n",
                       extends="project-sidecar"),
               change={"changed": True, "what": "8 decimals, not 6"})
ds.assimilate(s.project, str(s.work))
compares = [c_ for c_ in c.calls() if "CURRENT:" in c_]
classifies = [c_ for c_ in c.calls() if "CURRENT:" not in c_]
check("the comparison names a model", 1, len(compares))
check("and it is the cheap one", True, f"--model {ds.COMPARE_MODEL}" in compares[0])
check("the classifier is asked once", 1, len(classifies))
check("and keeps whatever model the session uses", False, "--model" in classifies[0])
c.restore()
ds.DRY_RUN = False


# Thrashing, end to end. Bob adapted the team's memory, his dream reworded it, and
# it is now a candidate again. The facts are identical, so no PR may be opened —
# otherwise Alice adapts Bob's wording, her dream rewords it, and round it goes.
s = Sandbox()
s.shared("project-sidecar", "the sidecar rounds USDC",
         body="The sidecar rounds USDC to 6 decimals before writing to Postgres.")
s.local("project-sidecar",
        body="USDC is rounded by the sidecar to 6 decimals, before it writes to Postgres.")
s.settle()
c = FakeClaude(verdict("project-sidecar",
                       "---\nname: project-sidecar\n---\n\n"
                       "USDC is rounded by the sidecar to 6 decimals, before it writes to Postgres.\n",
                       extends="project-sidecar"),
               change={"changed": False, "what": None})
check("a reworded copy of a team memory opens no PR",
      "1 evaluated, none met the bar, 0 blocked", ds.assimilate(s.project, str(s.work)))
check("and the team's wording is untouched", True,
      "The sidecar rounds USDC to 6 decimals" in (s.team / "project-sidecar.md").read_text())
c.restore()

# The other half: a correction has to get through, and it is one character.
s = Sandbox()
s.shared("project-sidecar", "the sidecar rounds USDC",
         body="The sidecar rounds USDC to 6 decimals before writing to Postgres.")
s.local("project-sidecar",
        body="The sidecar rounds USDC to 8 decimals before writing to Postgres.")
s.origin()
s.settle()
ds.DRY_RUN = True
c = FakeClaude(verdict("project-sidecar",
                       "---\nname: project-sidecar\n---\n\n"
                       "The sidecar rounds USDC to 8 decimals before writing to Postgres.\n",
                       extends="project-sidecar"),
               change={"changed": True, "what": "rounds to 8 decimals, not 6"})
branch = branch_of(ds.assimilate(s.project, str(s.work)) or "")
check("a corrected number does open a PR", True,
      "8 decimals" in blob_of(s, branch, ".collective-memory/project-sidecar.md"))
c.restore()
ds.DRY_RUN = False

# A memory someone pulled is the team's own text back again. Assimilating it would
# open a pull request whose entire diff is their name landing in sharedBy.
s = Sandbox()
s.shared("project-grafana", "Grafana tenants are separated by org id",
         body="Tenants are separated by org id.")
pulled = (s.team / "project-grafana.md").read_text()
(s.memory / "project-grafana.md").write_text(pulled)
s.settle()
c = FakeClaude(verdict("project-grafana", pulled, extends="project-grafana"))
check("a pulled memory is never assimilated back",
      "1 evaluated, none met the bar, 0 blocked", ds.assimilate(s.project, str(s.work)))
c.restore()


# ------------------------------------------------------------------- lineage
#
# What adapt records, and what assimilate does with it. The classifier is only ever
# shown corpus names and descriptions — never bodies — so a pulled memory that
# /dream has since merged and renamed has nothing left to match on, and the same
# fact lands in the shared corpus a second time. Lineage makes that a fact
# instead of a guess.

check("lineage reads pulledFrom out of the metadata block", "project-grafana",
      ds.lineage("---\nname: mine\nmetadata:\n  type: project\n"
                 "  pulledFrom: project-grafana\n---\n\nBody.\n"))
check("a memory nobody pulled has no lineage", None,
      ds.lineage("---\nname: mine\nmetadata:\n  type: project\n---\n\nBody.\n"))

s = Sandbox()
s.shared("project-grafana", "Grafana tenants are separated by org id",
         body="Tenants are separated by org id.")
shared_file = s.team / "project-grafana.md"
shared_file.write_text(ds.stamp(shared_file.read_text(), "project-grafana"))
taken = ds.take(str(s.work), "project-grafana")
check("take records where the memory came from", "project-grafana", ds.lineage(taken))
check("take drops the team's sharers", False, "sharedBy" in taken)
check("take drops the team's assimilation date", False, "promotedAt" in taken)
check("take keeps the memory body", True, "Tenants are separated by org id." in taken)
check("take leaves the description alone", True,
      "Grafana tenants are separated by org id" in taken)
check("take is what adapt writes, so it must be clean", [], ds.scan(taken))

# The duplicate this exists to prevent: dream merged the pulled memory into a
# file of its own and renamed it, so its stem no longer matches anything in the
# corpus and the classifier returns no `extends`.
s = Sandbox()
s.shared("project-grafana", "Grafana tenants are separated by org id",
         body="Tenants are separated by org id.")
(s.memory / "project-observability.md").write_text(
    "---\nname: project-observability\ndescription: how tenants are split\n"
    "metadata:\n  type: project\n  pulledFrom: project-grafana\n---\n\n"
    "Tenants are separated by org id, and the alerting rules follow.\n")
s.origin()
s.settle()
ds.DRY_RUN = True
c = FakeClaude(verdict("project-observability",
                       "---\nname: project-observability\nmetadata:\n"
                       "  type: project\n  pulledFrom: project-grafana\n---\n\n"
                       "Tenants are separated by org id, and the alerting rules follow.\n"))
tree = tree_of(s, branch_of(ds.assimilate(s.project, str(s.work)) or ""))
check("a renamed pulled memory extends its origin", True,
      ".collective-memory/project-grafana.md" in tree)
check("and never files the same fact twice", False,
      ".collective-memory/project-observability.md" in tree)
c.restore()
ds.DRY_RUN = False

# Lineage is local bookkeeping. It says nothing to anyone else and must not
# survive the trip back out, the same way sharedBy and originSessionId do not.
s = Sandbox()
s.local("project-a", body="The receiver writes to Postgres before the sidecar reads it.")
s.origin()
s.settle()
ds.DRY_RUN = True
c = FakeClaude(verdict("project-a",
                       "---\nname: project-a\nmetadata:\n  type: project\n"
                       "  pulledFrom: project-grafana\n---\n\nA durable fact.\n"))
branch = branch_of(ds.assimilate(s.project, str(s.work)) or "")
check("lineage never reaches the shared corpus", None,
      ds.lineage(blob_of(s, branch, ".collective-memory/project-a.md")))
c.restore()
ds.DRY_RUN = False

del os.environ["COLLECTIVE_GRAPHIFY"]


# ------------------------------------------------------------------ provenance

MEMORY = """---
name: project-docker-stack
description: how the stack is composed
metadata:
  node_type: memory
  type: project
  originSessionId: 18b4113a-7c80-4b59-8e84-13318cc0f92a
  modified: 2026-07-23T02:29:07.030Z
---

The receiver talks to Postgres. See [[project-grafana-tenant-separation]].
"""

out = ds.stamp(MEMORY, "project-docker-stack")
check("stamp drops the origin session id", False, "originSessionId" in out)
check("stamp drops the local modified time", False, "modified:" in out)
check("stamp records who shared it", True, "sharedBy: [" in out)
check("stamp records when", True, "promotedAt:" in out)
check("stamp keeps the memory body", True, "The receiver talks to Postgres." in out)
check("stamp keeps wikilinks", True, "[[project-grafana-tenant-separation]]" in out)
check("stamp keeps the description", True, "description: how the stack is composed" in out)
check("stamp nests provenance under metadata", True, "\n  sharedBy: [" in out)

prior = "---\nname: x\nmetadata:\n  sharedBy: [alice@example.com]\n---\n\nOld.\n"
out = ds.stamp(MEMORY, "project-docker-stack", existing=prior)
check("stamp keeps prior sharers when extending", True, "alice@example.com" in out)

# A second assimilation of an already-stamped file must not stack duplicate keys.
out = ds.stamp(ds.stamp(MEMORY, "project-docker-stack"), "project-docker-stack")
check("stamp is idempotent on sharedBy", 1, out.count("sharedBy:"))
check("stamp is idempotent on promotedAt", 1, out.count("promotedAt:"))

# Whatever stamp emits is what lands in the repo, so it has to survive the
# scanner too — a body the model rewrote is not trusted just because it parsed.
check("stamped output is scannable", [], ds.scan(out))


# -------------------------------------------------------------------- graphify
#
# No working graphify backend is assumed, so these drive a stub on PATH. That
# covers everything collective is responsible for — where the graph is built,
# whether a silent failure is noticed, what gets asked, what it costs — and
# nothing about graphify's own extraction quality, which is graphify's to test.

class Graphify:
    """A stub `graphify` on PATH that logs how it was invoked."""

    def __init__(self, builds_graph=True):
        self.dir = Path(tempfile.mkdtemp())
        self.log = self.dir / "calls.log"
        graph = ('mkdir -p graphify-out && printf "{}" > graphify-out/graph.json'
                 if builds_graph else 'true')
        # Exit 0 either way. That is the real graphify's behaviour when every
        # semantic chunk fails, and the reason a return code cannot be trusted.
        (self.dir / "graphify").write_text(
            "#!/usr/bin/env bash\n"
            f'{{ pwd; printf "%s\\n" "$*"; }} >> "{self.log}"\n'
            f"{graph}\n"
            'if [ "$1" = "query" ]; then echo "overlaps with project-docker-stack"; fi\n'
            "exit 0\n")
        (self.dir / "graphify").chmod(0o755)
        self.prev = os.environ["PATH"]
        os.environ["PATH"] = f"{self.dir}:{self.prev}"

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def restore(self):
        os.environ["PATH"] = self.prev


s = Sandbox()
s.shared("project-docker-stack", "the stack is three compose files")
s.local("project-docker-notes")
s.settle()
pending = ds.candidates(s.project)

g = Graphify(builds_graph=True)
context = ds.graphify_context(s.team, pending)
check("graph context names the candidate", True, "project-docker-notes" in context)
check("graph context carries the neighbour", True,
      "overlaps with project-docker-stack" in context)
check("the graph is built with extract", True, "extract ." in g.calls())
check("the candidate is what gets queried", True,
      "candidate-project-docker-notes" in g.calls())
check("graphify never runs inside the repo", False, str(s.team) in g.calls())
check("no build artifacts land in the shared directory", False,
      (s.team / "graphify-out").exists())
g.restore()

# The failure this was rewritten to catch: graphify exits 0 with every chunk
# failed and no graph on disk. Trusting the return code made the whole feature a
# silent no-op through a full end-to-end run.
g = Graphify(builds_graph=False)
check("a graphless run contributes nothing", "", ds.graphify_context(s.team, pending))
check("a graphless run is never queried", False, "query" in g.calls())
g.restore()

g = Graphify(builds_graph=True)
os.environ["COLLECTIVE_GRAPHIFY"] = "0"
check("COLLECTIVE_GRAPHIFY=0 skips it", "", ds.graphify_context(s.team, pending))
check("COLLECTIVE_GRAPHIFY=0 runs nothing", "", g.calls())
del os.environ["COLLECTIVE_GRAPHIFY"]
g.restore()

empty = Sandbox()
g = Graphify(builds_graph=True)
check("an empty corpus needs no graph", "", ds.graphify_context(empty.team, pending))
check("an empty corpus runs nothing", "", g.calls())
g.restore()

# Every candidate costs a model call, so the cap has to hold — and be disclosed
# rather than silently dropping the tail.
s2 = Sandbox()
s2.shared("project-seed", "something already shared")
for i in range(11):
    s2.local(f"project-{i}")
s2.settle()
g = Graphify(builds_graph=True)
ds.MAX_GRAPH_QUERIES = 3
context = ds.graphify_context(s2.team, ds.candidates(s2.project))
check("the query cap holds", 3, g.calls().count("query"))
check("the cap is disclosed, not silent", True,
      "8 further candidates not queried" in context)
ds.MAX_GRAPH_QUERIES = 8
g.restore()

sys.exit(FAILED)
