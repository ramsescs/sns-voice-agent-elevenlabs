# Git for Personal Projects — A Practical Guide

A cheatsheet of habits that keep a solo or small project's history clean,
recoverable, and easy to reason about. Each rule comes with the **why** —
because a practice you understand is one you'll actually keep.

The golden thread running through all of it: **your git history is a tool for
your future self.** Six months from now you'll want to know *why* a line
changed, *when* a bug was introduced, and *what* a feature actually touched.
Every habit below buys you that.

---

## 1. Branching

### One branch per unit of work

Create a new branch for each feature, fix, or task — not a branch you reuse
for everything.

```bash
git checkout main && git pull          # start from an up-to-date main
git checkout -b feat/audit-log          # branch for one specific task
```

**Why it matters:**

- **`main` stays always-working.** If a feature is half-finished or broken,
  the mess is quarantined on its branch. You can always check out `main` and
  have something that runs.
- **Each branch maps to one reviewable change.** When you open a PR, its diff
  shows exactly what that one task touched — nothing else. Bundling three
  features into one branch destroys this: there's no way to review, revert, or
  understand them separately.
- **You can switch context cheaply.** Need to drop everything and fix an
  urgent bug? Branch off `main`, fix it, merge it — your half-done feature
  waits untouched on its own branch.

### Name branches so they're self-explanatory

A common convention is a `type/short-description` prefix:

| Prefix   | Use for                          |
| -------- | -------------------------------- |
| `feat/`  | new features                     |
| `fix/`   | bug fixes                        |
| `docs/`  | documentation only               |
| `chore/` | tooling, config, dependencies    |
| `refactor/` | restructuring without behavior change |

Example: `feat/004-audit-log`, `fix/set-engine-off-by-one`.

**Why:** `git branch` becomes a readable to-do list instead of a pile of
`test`, `test2`, `new-stuff`. The prefix also tells you at a glance whether a
branch is risky (a `feat/` touching core logic) or safe (a `docs/` typo fix).

### Delete branches after merging

```bash
git branch -d feat/audit-log            # delete local
git push origin --delete feat/audit-log # delete remote
```

**Why:** merged branches are dead weight. Deleting them keeps `git branch`
showing only *active* work, so you never have to wonder "did I already merge
that?"

---

## 2. Commits

### Commit small, commit often — but keep each commit coherent

A good commit is **one logical change**. Not "a day's work," not "half a
function" — one complete, self-contained step.

**Why:**

- **Bisecting works.** `git bisect` can pinpoint the exact commit that
  introduced a bug — but only if each commit is a small, working step. One
  giant "implemented everything" commit tells you nothing.
- **Reverting is surgical.** If one change turns out wrong, you can revert
  just that commit without unpicking unrelated work tangled into it.
- **The history reads like a story.** Someone (usually future-you) can scroll
  the log and follow the reasoning step by step.

### Write messages that explain *why*, not *what*

The diff already shows *what* changed. The message should capture intent.

```
Bad:   "update set_engine.py"
Bad:   "fix bug"
Good:  "Route missing-data cases upward instead of to self-care

        Under-triage is the dangerous error, so an incomplete interview
        must fail toward more urgent care, not less."
```

Format: a **short imperative subject line** (~50 chars, "Add X" not "Added
X"), a blank line, then a body explaining the reasoning if it isn't obvious.

**Why:** in a year, the *what* is recoverable from the code but the *why* is
gone forever unless you wrote it down. The message is the only place the
reasoning survives.

### Stage explicitly — never blind-add everything

```bash
git add src/triage/set_engine.py tests/test_set_engine.py   # name the files
git status                                                   # verify what's staged
```

Avoid `git add -A` and `git add .` as reflexes.

**Why:**

- **You avoid bundling unrelated changes.** Blind-adding sweeps up every
  modified file — including ones from a *different* task you hadn't finished —
  into one commit. (This exact mistake is easy to make and annoying to undo.)
- **You avoid committing secrets and junk by accident.** A stray `.env`,
  an API key, a debug scratch file, a 200 MB data dump — `git add .` grabs them
  all. Naming files (or reviewing `git status` before committing) is your last
  checkpoint.

Always run `git status` (and ideally `git diff --staged`) right before
committing to confirm exactly what's going in.

---

## 3. Pull Requests

### When to use a PR vs. commit straight to `main`

| Change type | Where |
| ----------- | ----- |
| Feature with tests / acceptance criteria / anything that could break | **branch + PR** |
| Code touching core logic | **branch + PR** |
| Config tweak, docs fix, typo, `.gitignore` line | **direct to `main` is fine** |

**Why the split:** PRs are a checkpoint, and checkpoints have a cost (ceremony,
time). Spend that cost where a mistake would hurt — real code — and skip it for
a one-line doc fix that can't break anything. Over-processing trivial changes
just trains you to click "merge" without looking, which defeats the point.

### What a PR is *for*, even solo

A PR is a **structured pause before code becomes permanent**. Even with no
reviewer, it gives you:

- **A whole-change diff** — you review the feature as one unit, catching
  leftover debug prints, a forgotten `TODO`, an accidental file.
- **A place for CI to run** — tests/linters run on the branch before it can
  pollute `main`.
- **A written record** — the PR description ("what & why") becomes durable
  project documentation, linked to the exact commits.

**Why it matters even without a second person:** you are your own reviewer, and
reviewing a clean diff on GitHub catches things you'll miss while heads-down
writing the code.

### When to merge

Merge when:

- the change's acceptance criteria are met (tests green),
- CI passes,
- you've read the diff once more and nothing looks off.

Then merge, pull `main` locally, and start the next branch from a fresh `main`:

```bash
git checkout main && git pull
```

**Why pull immediately after:** your local `main` is now behind the remote (it
doesn't have the just-merged commit). Pulling before branching again means your
next branch starts from the true latest state — avoiding needless conflicts.

### Don't reuse a branch after its PR is merged

Once a branch's PR is closed/merged, that branch has done its job. Start new
work from a **new branch off `main`**.

**Why:** a merged branch is "behind" `main` and semantically finished. Piling
new commits onto it creates a confusing branch that's part-merged,
part-not, and its next PR diff will be muddled.

---

## 4. `.gitignore` — set it up first

Before your first commit, add a `.gitignore` so generated and sensitive files
never enter history.

Typical entries for a Python project:

```gitignore
# Secrets — NEVER commit
.env
*.key

# Python
__pycache__/
*.pyc
.venv/
venv/
*.egg-info/

# OS / editor cruft
.DS_Store
.idea/
.vscode/
```

**Why it's important:**

- **Secrets are near-impossible to fully remove.** Once an API key is
  committed and pushed, it's in the history *and* possibly cloned/forked
  elsewhere. Deleting it in a later commit does **not** remove it from history
  — you must assume it's compromised and rotate the key. Preventing the commit
  is the only clean fix.
- **Generated files create noise and conflicts.** `__pycache__`, build
  artifacts, and virtualenvs change constantly and differ per machine.
  Committing them floods every diff with irrelevant churn and causes merge
  conflicts over files nobody edits by hand.

---

## 5. Working with the remote

### Pull before you start, push when you pause

```bash
git pull        # before starting a session / new branch
git push        # after committing meaningful work
```

**Why:**

- **Pulling first** keeps you working on top of the latest state, minimizing
  conflicts (matters even solo if you use more than one machine).
- **Pushing regularly** is your **off-machine backup**. A branch that only
  exists on your laptop is one spilled coffee away from gone. Pushed work is
  safe.

### Never force-push a shared branch

`git push --force` rewrites remote history. On a branch someone else (or
another clone) has, it destroys their work.

**Why / when it's OK:** force-pushing is *fine* on a private feature branch
only you use, e.g. after cleaning up commits before a PR. It is **never** OK on
`main` or any branch others build on. Prefer `--force-with-lease` over
`--force` — it refuses to overwrite if the remote changed unexpectedly, acting
as a safety catch.

---

## 6. Undo & recovery — the safety net

Knowing you can undo almost anything makes git far less scary.

| Situation | Command | Notes |
| --------- | ------- | ----- |
| Unstage a file (keep changes) | `git restore --staged <file>` | |
| Discard uncommitted changes in a file | `git restore <file>` | **destroys work** — be sure |
| Undo last commit, keep changes staged | `git reset --soft HEAD~1` | commit vanishes, edits stay |
| Undo last commit, keep changes unstaged | `git reset HEAD~1` | |
| Revert a *pushed* commit safely | `git revert <hash>` | makes a *new* commit that undoes it |
| Save work-in-progress without committing | `git stash` / `git stash pop` | add `-u` to include untracked files |
| See where HEAD has been (recover "lost" commits) | `git reflog` | your ultimate undo history |

**Why `revert` for pushed commits, not `reset`:** `reset` rewrites history,
which is destructive on anything already pushed/shared. `revert` adds a new
commit that cancels the old one — history stays intact and honest, and nobody's
clone breaks.

**Why `reflog` is a lifesaver:** even after a bad `reset` or a deleted branch,
git remembers where `HEAD` pointed. `git reflog` shows those points so you can
`git checkout` or `git reset` back to a "lost" commit. Very little is truly
unrecoverable in git — this is why.

**Before any destructive command** (`reset --hard`, `checkout` over changes,
`clean`), run `git status` first and `git stash -u` anything you're unsure
about. Stashed work is trivially recoverable; discarded work often isn't.

---

## 7. A clean end-to-end workflow (putting it together)

```bash
# 1. Start fresh from the latest main
git checkout main && git pull

# 2. Branch for one specific task
git checkout -b feat/004-audit-log

# 3. Work in small, coherent commits
#    (edit files...)
git add src/triage/audit.py tests/test_audit.py   # stage explicitly
git status                                          # verify
git commit -m "Add JSON audit record per interaction"
#    (more edits, more small commits...)

# 4. Push the branch (backup + enables a PR)
git push -u origin feat/004-audit-log

# 5. Open a PR, let CI run, review your own diff
gh pr create

# 6. Merge when green and reviewed
gh pr merge --merge

# 7. Return to a fresh main, delete the dead branch
git checkout main && git pull
git branch -d feat/004-audit-log
```

---

## Quick reference card

```
Start work:     git checkout main && git pull
                git checkout -b feat/thing

Save work:      git add <specific files>
                git status                # always verify
                git commit -m "Imperative subject explaining why"
                git push

Finish:         gh pr create → review → gh pr merge --merge
                git checkout main && git pull
                git branch -d feat/thing

Oh no:          git status                # look before you leap
                git stash -u              # park uncertain changes
                git reflog                # find "lost" commits
                git revert <hash>         # undo a PUSHED commit safely
```

---

### The three habits that matter most

If you remember nothing else:

1. **One branch per task** → clean, reviewable, revertible history.
2. **Stage explicitly + read `git status` before committing** → no secrets, no
   accidental bundles.
3. **`revert` (not `reset`) anything already pushed** → never rewrite shared
   history.

Everything else is refinement on top of these three.
