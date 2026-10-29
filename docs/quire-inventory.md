# Inventory of bats-lang/quire's rules: what is pitboss's, what is quire's

Tickets: dev-skill-up/pitboss#41 and #45. Source: bats-lang/quire `main` (3c47255) at the
time of writing (`CLAUDE.md`, the 20 files of `.claude/rules/`, `.claude/orchestration.md`,
the 2 files of `.claude/agents/` and the 3 files of `.claude/skills/`), and the 24 open quire
pull requests. No file is moved by these tickets; each move is a ticket of its own, filed
from this list.

## The test and the verdicts

The test is: would the owner's ruling be the same if the project were written in Rust?

* `pitboss`: yes for the whole text. It moves whole.
* `split`: yes for some paragraphs. The row names which move and which stay.
* `quire`: no. It stays, with the quire-specific reason in one line.

A row that is `pitboss` or `split` cites the pitboss file it lands in. Two files are new:

* `plugins/pitboss/skills/sweep/references/engineering.md` (new): rulings on code, tests and
  errors that hold in any language.
* `plugins/pitboss/skills/sweep/references/ci.md` (new): rulings on CI, pins, caches and
  checking before a push that hold for any project on GitHub.

`plugins/pitboss/skills/sweep/references/rules.md` already states: research before design
("How decisions are made"), additive API changes and one version of overlap ("Published
APIs"), the order of work and priorities ("Agents and slots", "Tickets"), evidence and
reviews ("Reviews"), checkouts ("Checkouts and disk"). A row that lands there says so, and
the quire text shrinks to a pointer. A row of the sections that follow says "already there"
for content a pitboss reference holds today, and "owed" for content no pitboss file holds yet
(`python3 -I docs/quire-inventory-landing.py`, run at the root of this repository, checks both
claims against the files, and that no text a row says stays in quire is in a pitboss file;
`sh docs/quire-inventory-evidence.sh`, run as its header says, prints the row counts).

## quire's CLAUDE.md, by section (13 sections)

| # | Section | Verdict | Lands in, or why it stays |
|---|---|---|---|
| 1 | Decisions are made by research, not left to the human | split | Moves: every paragraph but the last sentence (research, not the human, settles a design choice; judgement is what is left after the research; "if nothing comparable can be found, say so") to `rules.md`, "How decisions are made" (which holds only the one-line "Research before design" today). Stays: the last sentence, "The quality rules below (the proofs, the static tests, the e2e suite) still hold" (it names quire's own rules) |
| 2 | A proof is a proof | split | Moves: the first paragraph (a requirement that says proof means a static proof) and "a claim that is only tested is said to be tested, and the proof is still owed", to `engineering.md`. Stays: the paragraph on trusted primitives, `praxi`, `assume`, `$UNSAFE` and the array package (ATS2 proofs) |
| 3 | Comments name their area by keyword | pitboss | `engineering.md` |
| 4 | Names are words | split | Moves: the rule that names are words and that terse names collide, and the loop-index exception, to `engineering.md`. Stays: the examples about element ids and numbered-id prefixes of 16 bytes (quire's DOM ids) |
| 5 | Priorities | split | Moves: p0 to p3 and "Order of work" (worker in progress, open PR, merge, then tickets, blocked tickets, no downgrades without the owner) to `rules.md`, "Agents and slots" and "Tickets" (largely there already). Stays: the paragraph "The Android release is not a priority" (Android release) |
| 6 | Pipeline and tooling improvements belong in bats or pwa | split | Moves: "We do not write shell scripts (or any non-bats code of our own) unless all other avenues are exhausted" (as "our own language, not shell") and "No mtimes in freshness", to `engineering.md` and `ci.md`. Stays: the first two paragraphs (what belongs to bats and to pwa, quire#623, #635, #637, #646, #731) |
| 7 | Breaking changes keep at least one published version of overlap (#762) | split | `rules.md`, "Published APIs" paraphrases the rule and lacks these, which move there so nothing is lost when quire's copy is deleted: the p2 ticket for each dependent's move to the new form, with the removal blocked on them (owner, 2026-10-27T15:31:29Z, transcript line 119703); "when it was filed is never a finding" (owner, 2026-10-25T05:27:02Z and 2026-10-25T00:11:51Z); the four dated owner quotes with their transcript lines (46303, 51253, 64376, 64396); the review checklist of both steps. Stays: the pointer to repository-prototype's CLAUDE.md and the sentences naming the brief templates in `.claude/orchestration.md` ("Overlap" and "Overlap check" lines) and `tests/static/guidelines.py` |
| 8 | CI is pinned | split | Moves: every input pinned in the source, a committed lock, CI never relocks, pins move only through a reviewed PR, the daily relock, no bot opens PRs, to `ci.md`. Stays: the names (`bats.lock`, `.github/bats-version`, `android.yml@<sha>`, Dependabot grouping, #996, the setup action) |
| 9 | No cache key is relied on for correctness (#622) | split | Moves: the first sentence (a restored cache is judged by the tool, never by the key that found it) to `ci.md`. Stays: the bats stamp, the memo and the key format `quire-<name>@<commit>` |
| 10 | Check locally before every push | split | Moves: check locally before a push, a run over a population is a random sample with a printed seed and the PR says the sample and why it suffices, the checkout stays, to `ci.md` and `rules.md`, "Checkouts and disk". Stays: `bats check`, 10 to 15 minutes cold, `qsweep clean`, the compiler setup |
| 11 | Evidence, red tests and CI | split | Moves: evidence for every claim in the PR body, a red test is root-caused, "it passed again" is not a cause, the author owns CI until green, a reviewer starts only on a green exact head, to `rules.md`, "Reviews" and "Briefs and workers" (largely there already). Stays: the last sentence naming `.claude/agents/*.md`, `orchestration.md` and `tests/static/guidelines.py` |
| 12 | The version is the commit's | split | Moves: a version is the commit's, never the build's, so one commit always gives one version, to `engineering.md`. Stays: the pointer to `.claude/rules/release.md` |
| 13 | Play release | quire | Google Play and `check.yml`'s `play-internal` job |

## quire's `.claude/rules/`, by file (20 files)

| File | Verdict | Lands in, or why it stays |
|---|---|---|
| `backup-errors.md` | split | Moves: the rule of "Every error says what to do (#360)" (a failure is said with a next step, the unexpected is its own outcome) to `engineering.md`, entry "Failures and outcomes are said" (one entry, shared with the `interface.md` and `sync.md` rows). Stays: the banner, `notice.bats`, Reopen Quire, Copy details, the backup section (#362), the protected book section (#427) |
| `backup-write-answer.md` | quire | Android Auto Backup file and bridge's `backup_write_answer` |
| `book-memory.md` | quire | Quire's page arenas and EPUB pathological structure |
| `book-text.md` | quire | Encodings, series and CSS sizes of EPUB text |
| `cfi.md` | quire | EPUB CFI |
| `ci.md` | split | Moves: "Only the groups a change can affect run" draft bullet (a draft PR runs no costly job) and "A run over a population is a sample" bullet of "Checking locally before a push", to `ci.md`. Stays: every other section: pins and relock names, the Android lock, the compiler's cache (bats stamp), static fixtures, solver fixtures, the merge queue (this repository's runner pool and 60 minute window), Node's packages, the mutation check (ATS2 proofs), the `plan` job's table, the local commands, the flight recorder on a local machine |
| `dictionaries-catalogues.md` | quire | StarDict dictionaries and OPDS catalogues |
| `e2e.md` | split | Moves: the bullet "A test never waits in real time for a moment of the app's own" of "No flaky waits", the first paragraph of "A worker's machine matches CI (#713)" ("This machine lacks X is never a reason for a spec to be skipped"), to `engineering.md` and `rules.md`, "Briefs and workers". Stays: projects and groups, `clickControl`, `rawMouse`, the Playwright pin, the tool list, two books, the stall watch, the flight recorder (Playwright, Chromium and the kernel's tracefs) |
| `epub-format.md` | quire | EPUB archive, spine and package rules |
| `epub-media.md` | quire | EPUB narration, media, fonts and MathML |
| `interface.md` | split | Moves: "Failures are said, never dropped" (the rule, not the `notice.bats` names) to `engineering.md`, entry "Failures and outcomes are said" (the same entry as the `backup-errors.md` and `sync.md` rows). Stays: the stylesheet under proofs, `ui.bats`, "Nothing is lost at a click" (reader Undo and Trash), overlays and Back |
| `library-records.md` | quire | Quire's stored records, codec and Replace |
| `library-screen.md` | quire | The library screen |
| `platform.md` | quire | Quire's use of bridge's platform atoms |
| `reader-layout.md` | quire | Reader gestures, spreads and writing modes |
| `reader.md` | quire | Reader notes, positions and touch selection |
| `release.md` | split | Moves: the first sentence of "The version is the commit's" (the date of the commit, never of the build) to `engineering.md`. Stays: the rest (`YEAR.MONTH.DAY.SECONDS`, `bats_commit_*` facts, `versionName`, `versionCode`) and "Main goes to Play's internal testing" (Google Play) |
| `sync.md` | split | Moves: the rule of "Every outcome is said, and the unexpected as such (#334)" (an error is an outcome of its own, never folded into another, and what is not recognised is explicit) to `engineering.md`, entry "Failures and outcomes are said" (the same entry as the `backup-errors.md` and `interface.md` rows). Stays: the sync file, the services, the 30 second answer, Google, Dropbox and Nextcloud |
| `types.md` | split | Moves: "A choice is a datatype" rule (an int never encodes one of a fixed set of cases; "none" is an option, not -1) to `engineering.md`. Stays: "What allocates is linear" (wasm, ATS2 `datavtype`, `lincloptr1`) and the `case+` lint name |
| `vocabulary.md` | quire | The words-looked-up feature and its KOReader schedule |

Count: 20 files: 0 `pitboss`, 7 `split` (`backup-errors`, `ci`, `e2e`, `interface`, `release`,
`sync`, `types`) and 13 `quire` (`backup-write-answer`, `book-memory`, `book-text`, `cfi`,
`dictionaries-catalogues`, `epub-format`, `epub-media`, `library-records`, `library-screen`,
`platform`, `reader-layout`, `reader`, `vocabulary`). CLAUDE.md: 13 sections: 1 `pitboss`
(row 3), 11 `split` and 1 `quire` (row 13).

## quire's `.claude/orchestration.md`, by section (12 sections and the opening paragraph)

The file is the standing rules of the orchestrator. Every paragraph of it that is not about
quire's own tools is already in `rules.md` (the headings of `rules.md` follow the headings of
this file), so every row says "already there" and names what stays.

| File and section | Verdict | Lands in, or why it stays |
|---|---|---|
| `orchestration.md: (opening paragraph)` | split | Moves (already there): how the owner's words are marked, `(owner, <timestamp>)` verbatim in quotation marks and `(orchestrator, <date>)` for a rule drawn from them, and that the owner's words are never extended, to `rules.md`, "How a rule is written here". Stays: that the file is not under `.claude/rules/` or `.claude/skills/` (quire's layout) and the name of the lint that finds a marker that does not hold, `tests/static/guidelines.py` |
| `orchestration.md: Priorities` | split | Moves (already there): that the orchestrator works tickets in the order p0 to p3, to `rules.md`, "Tickets" (Priorities and Order of work). Stays: the pointer to quire's `CLAUDE.md` section "Priorities" and the Android-release hold it names (the `CLAUDE.md` row 5) |
| `orchestration.md: Agents and slots` | split | Moves (already there): the ten steps and the two bullets under step 9 (list the agents first, the free-slot order, a reviewer starts on a green exact head, the rows of the ledger are the agents that run, a slot is never held idle, an interrupt is not a stop, no predictive scheduling, the oldest ticket of the highest priority, reviewers are separate agents, the order of work of 2026-10-28, the cap is a target, an agent is stopped only when the owner asks), to `rules.md`, "Agents and slots" 1 to 13. Stays: `ListAgents` (Claude Code's tool name), `qsweep`'s `NEXT FOR A FREE SLOT` and `READY-FOR-REVIEW`, the file `/tmp/claude-0/slots.tsv` and the `slots` command, the hourly slot check, and the bats `src/` sentences of step 7 (one bats pull request in flight because it regenerates `bootstrap/c`; `rules.md` holds the general exception only) |
| `orchestration.md: Merge conflicts` | pitboss | `rules.md`, "Merge conflicts" (already there: all three bullets; `bootstrap/c` is "generated files" there) |
| `orchestration.md: Tickets` | split | Moves (already there): a ticket is split only for a reason that justifies it, a blocked ticket is not started, `Fixes` and `Refs`, an agent that stops before the ticket is done is not given it again, a flake ticket is closed only when the work was done, to `rules.md`, "Tickets" (the ban on giving the ticket again is "Agents and slots" 12). Stays: the sentence "Every worker brief carries the `No split:` line below" (a pointer into quire's briefs section), `guidelines.py` and `phrases.tsv` in the `Fixes` bullet, and the label name `human only` |
| `orchestration.md: Plan first, and two rounds of changes needed` | split | Moves (already there): two reviews that ask for changes mean a plan first, an Opus ruling comes before the pause, a PR starts as a draft whose body is a Plan and an Execution, a plan that needs a long run for its evidence is invalid, to `rules.md`, "Plan first, and two rounds of changes needed". Stays: the label name `paused-owner` (`rules.md` says "a pause label") |
| `orchestration.md: Briefs and the machine` | split | Moves (already there): a brief copies the Done-when word for word and offers no alternative, what every worker and reviewer brief says, the `Design check:`, `Push:`, `Sample:`, `No split:` and `Compiler:` lines, the hand-back form, "This machine lacks X" is never an excuse, `/dev` is not written to, checked-in code does not depend on `sed`, disk is a shared allowance and cleaning it is the orchestrator's job, checkouts persist, to `rules.md`, "Briefs and workers" and "Checkouts and disk". Stays: the commands `guidelines.py --brief` and `--text`, the `Overlap:` and `Overlap check:` lines (`CLAUDE.md` row 7), the `Expects:` line (bats fixtures `--bless`), the `Affected:` line (`ci-groups.py`), the `Tracefs:` line (e2e on a restarted container), and the pointer to quire's "Check locally" section |
| `orchestration.md: Pushing and merging` | split | Moves (already there): check the runner pressure before a push or a merge, a PR body starts with `Fixes #N` ("Agents and slots" 10), a worker never waits for CI ("Briefs and workers"), a PR merges only after an independent review of its head, no stacked PRs, no hook is installed by hand, many small PRs go in batches with a pressure check, a PR that adopts new package versions relocks, to `rules.md`, "Pushing and merging". Stays: `qsweep pressure` and `qsweep push`, "Quire CI-triggering actions are 15 minutes apart" and "bats PRs that touch `src/` are serialized" (this repository's runner pool and bootstrap regeneration), "At most 2 merge-queue entries" and `supersede.yml`, the gated repositories (bridge, pwa, capacitor-plugins), "Use merge, not squash", `enable_pr_auto_merge`, and `bats lock --repository <dir>` |
| `orchestration.md: Checkouts` | split | Moves (already there): the orchestrator's checkouts stay on the default branch with a clean tree and are fast-forwarded at the start of every session and after every compaction, to `rules.md`, "Checkouts and disk". Stays: the list of the 12 repositories and the 14 files an agent loads, `/home/user/<repo>`, quire#732 and `qsweep`'s `STRAY-WORK` |
| `orchestration.md: The orchestrator's own working rules (not the owner's)` | split | Moves (already there): nobody deletes the persistent checkout, and no hook is set up, to `rules.md`, "Checkouts and disk" and "Pushing and merging". Stays: the bullet on `.claude/skills/sweep/` (the stopgaps quire#751, bats#435 and quire#573), the 90 percent figure, and the sentence about the message the owner sent back, which is history and not guidance (`rules.md`, "How a rule is written here") |
| `orchestration.md: Published APIs` | split | Moves (already there): API changes are additive, and breaking changes have at least one version of overlap, to `rules.md`, "Published APIs". Stays: the incident that is the reason (process#62, pwa's archive, process#65), which is history |
| `orchestration.md: How decisions are made` | split | Moves (already there): research before design, no invented threat models, a proof is a proof (`engineering.md`), no mtimes and no shell of our own (`engineering.md`, `ci.md`), a limitation is removed and not admitted (`rules.md`, "Briefs and workers", "Not done is not done"), a tool of the process that fails is fixed and not shimmed, a review is never referred to the owner ("Agents and slots" 10), report outcomes by their evidence, the owner's preferences in the system prompt, an Opus worker predicts the owner's answer, the owner has no access to the machine, a mechanical problem across repositories is fixed by a script, a rule file holds guidance and not history, no agent says it did not look, to `rules.md`, "How decisions are made", "Reviews" and "Briefs and workers". Stays: quire#646, the sentence on the `bootstrap/c` regenerate-and-compare check, the settings file `.claude/settings.json`, and `phrases.tsv` |
| `orchestration.md: Open work` | quire | The `gh api` query for the open p0 tickets of the named bats-lang repositories |

## quire's `.claude/agents/` and `.claude/skills/`, by file (5 files)

`worker.md` and `reviewer.md` are the agent definitions a brief points at ("the worker rules of
the repository"). Research for where `worker.md` lands: `rules.md`, "Briefs and workers",
"Reviews" and "Tickets", `slots.md`, "Briefs", and `engineering.md` already hold every
paragraph of it that is not quire's, so a `worker.md` in pitboss would copy them and no file is
new. `adversarial-review.md` is the file a started reviewer reads, so `reviewer.md` lands there.

| File | Verdict | Lands in, or why it stays |
|---|---|---|
| `.claude/agents/worker.md` | split | Moves (already there): the ticket's Done-when is the standard and is never narrowed, `Fixes` only when every item is done, one ticket in one PR and the owner's reasons to split, a blocked ticket is not started, additive API changes, every sum is a datatype with named constructors, a design check before building, non-bats code names the avenue it exhausted, a checkout of your own that stays, local actions are short and a run over a population is a seeded sample, a run is never repeated to count failures, evidence for every claim in the PR body, a red test is root-caused and a class of failure has a case that fails when it occurs, push after every commit, never wait for CI, the PR body form (`Fixes #N`, a `Head:` line, an Evidence section), do not merge, the draft PR with a Plan and an Execution, the hand-back form and its not-done form, finish inside the turn, `/dev` and `sed`, to `rules.md`, "Agents and slots", "Tickets", "Merge conflicts" (the `Head:` line), "Briefs and workers", "Reviews", "Checkouts and disk" and "Published APIs", `slots.md`, "Briefs", `engineering.md` and `ci.md`. Stays: `library.bats` and the bound on data read into one value (ATS2 and the stored shelf), `BATS_SLOTS=1` and the cold first build, the `Affected` paragraph (`ci-groups.py`, quire#957), the tracefs command (quire#765, quire#958), `--bless` (bats#522), `qsweep push`, the regeneration of `bootstrap/c`, `guidelines.py --pr-body` and `text-lint.yml` with the footer the proxy rewrites, the commit trailers (the session supplies them), and the 4-core machine |
| `.claude/agents/reviewer.md` | split | Moves: a reviewer runs nothing, reads the design, starts only on a green exact head, is a separate agent, gives one of two verdicts against the Done-when, offers no way out, backs each finding with evidence, does not object to a phrase that does no harm, does not block on work the PR leaves alone, grades the Plan and the Execution on lines of their own, takes a green relock with a quick check, to `adversarial-review.md` and `rules.md`, "Reviews" (already there, except the items landed by pitboss#48). Landed by pitboss#48 (`docs/quire-inventory-landing.py` prints file and line): the hand-back `NOT STARTED: <check> is <state> at <sha>`, "if you wrote any part of the change, say so and stop", "report CI by name", "once non-bats is decided the choice among tools needs no justification" (`engineering.md`), "do not push, merge or edit the PR", "hand back after posting, with the comment's URL", "paraphrase a phrase you object to, never reproduce it", all to `adversarial-review.md`. Stays: the `tools:` line (Claude Code tool names), quire's first line `Independent review (a separate reviewer agent, not the author) of head <sha>` (a form in pitboss's configuration, `pitboss review-form`) and its footer, `qsweep` and the `text-lint` status, the `ci-groups.py` evidence check (quire#957), and the `library.bats` stored-format exception |
| `.claude/skills/sweep/SKILL.md` | quire | The description of the two stopgap scripts, their install line and the quire#751, bats#435 and quire#573 notes; pitboss's own `SKILL.md` and `sweep.md` say what its markers mean, and the quire file goes when quire uses pitboss |
| `.claude/skills/sweep/qsweep` | split | Moves (already there, as `pitboss sweep`, `pitboss pressure`, `pitboss clean-worktrees`): the PR line and what a head is ready for, the runner-pressure hold, stragglers and stale worktrees, the reminders, the order of the next item. Landed by pitboss#48: `qsweep push` (the pressure check and the push in one command) is in `SKILL.md` as `pitboss pressure <config> && git push`; pitboss has no single push command, `pitboss pressure` is the check. Stays: the script itself (non-bats code, bats#435), the list of repositories, quire's merge-queue source of the pressure, the `/home/user` paths and the review first line of quire |
| `.claude/skills/sweep/slots` | split | Moves (already there, as `pitboss slots`): the ledger commands `set`, `free` and `check`, the rows are the agents that run, reviewers included, and "check before you answer", to `slots.md`. Stays: the script itself (non-bats code, bats#435), the default path `/tmp/claude-0/slots.tsv` and quire#956 |

Count of the new rows, from `docs/quire-inventory-evidence.sh`: `.claude/orchestration.md` has
12 sections and the opening paragraph, 13 rows: 1 `pitboss`, 11 `split`, 1 `quire`.
`.claude/agents/` and `.claude/skills/` have 5 files, 5 rows: 0 `pitboss`, 4 `split`, 1 `quire`.

## Open quire pull requests that change a `pitboss` or `split` file or section

Verdict words: closes (all its changes are moved content), shrinks (names what stays), stays
(it changes only text that stays in quire). No open PR closes: each also changes code, a
workflow, a fixture or text that stays.

| PR | Title | Changes (verdict row) | Result |
|---|---|---|---|
| 1035 | The Android version code is the commit count plus an offset | `release.md` (split) | stays: the version code is `versionCode` and Play, which stay |
| 1034 | Reject fixtures name the one constructor they are about, and a lint refuses an expect that lists more (#984) | `ci.md` static fixtures (split) | stays: bats fixtures |
| 1031 | Place the selection toolbar outside the Android floating menu's band | `e2e.md` projects and groups (split) | stays: Playwright projects |
| 1023 | Replace the fixed waits of e2e/ with waits for an event (#985) | `e2e.md` section "Quarantine and race fixes" (split); stacked on 986 (base fix-976), it edits the third bullet of the section 986 adds, so 986 and 1023 are one addition, not two; and the same three additions as 986 to `agents/worker.md`, `agents/reviewer.md` and `orchestration.md` "Briefs and the machine" (rows split) | shrinks: the edited bullet moves to `engineering.md` with the section (whichever of 986 and 1023 lands first, the other follows it), and the race lines of the two agents and of the briefs section (root cause from the captured evidence, an injection that forces the losing order, no repeat to count failures, wait for an event) move to `rules.md`, "Reviews" and `engineering.md`; stays: `e2e/*.js` helpers, `stall-capture.spec.js`, `guidelines.py`, and the `Quarantine:` / `Race:` lines (`test.fixme`, "on every project") |
| 1021 | Slots: slots.tsv is authoritative on the number; remove the last count and refuse new ones | `orchestration.md` "Agents and slots" step 9, `skills/sweep/SKILL.md` and `skills/sweep/slots` (rows split, quire, split) | shrinks: "each taking a row of the ledger like any work" moves to `rules.md`, "Agents and slots" 4 (it already says reviewers are rows); stays: the `slots` script (`LEDGER MISSING`, quire#956), the `SKILL.md` text, `guidelines.py` and its test |
| 1018 | A capture reads a snapshot of the kernel ring and never stops it (#910) | `e2e.md` flight recorder (split) | stays: kernel tracefs |
| 1017 | Short jobs run locally, CI runs the rest; briefs may not run in the background or sleep (#911) | `CLAUDE.md` section 10, `ci.md` checking locally, `agents/worker.md` "Where you work, and how long a run is" (split) | shrinks: the rule on short jobs moves to `ci.md` and `rules.md`, "Briefs and workers" (local actions are short; already there), and the `worker.md` bullets that state it move with them; stays: the `worker.md` sentences on `BATS_SLOTS=1` and the cold first build, `guidelines.py`, `phrases.tsv`, the fixture |
| 1013 | orchestration.md: drop the rules moved to pitboss's sweep skill and link them | `orchestration.md` every row but "Priorities" and "Open work" (11 rows), `skills/sweep/SKILL.md`, `skills/sweep/qsweep` and `skills/sweep/slots` comments (rows quire, split, split) | shrinks: its deletions are the "Moves (already there)" of those 11 rows, and its kept bullets are the "Stays" of those rows (it keeps "Use merge, not squash", `paused-owner`, the `Expects:`, `Tracefs:` and `Overlap` lines, the bats `src/` paragraph, the 15 minute spacing); stays: the pointers it writes into `qsweep`, `slots` and `SKILL.md`, and the changes to `guidelines_test.py` and the two `.tsv` files; the one bullet it keeps that `engineering.md` holds is "A proof is a proof" |
| 1015 | ci.md: why a merge-queue entry is removed (#1026) | `ci.md` merge queue (split) | stays: this repository's merge queue |
| 1009 | e2e: a failed test keeps its trace, screenshot, DOM and console, and the job summary names them (#1008) | `e2e.md` (split) | stays: Playwright capture |
| 1007 | scripts/ci-groups.py local lists the fixtures a change affects (#1006) | `ci.md` checking locally (split) | stays: `ci-groups.py` and bats#570 |
| 997 | A watchdog report keeps the whole ring and says where it begins (#993) | `e2e.md` flight recorder (split) | stays: kernel ring |
| 991 | A draft runs plan and build; a head with no completed check run is not approved (#978) | `CLAUDE.md` section 11, `ci.md` draft bullet, `agents/reviewer.md` "When you start", `orchestration.md` "Agents and slots" step 3 and "Briefs and the machine" (split) | shrinks: "a head with no completed run is never approved" and the draft rule move to `rules.md`, `ci.md` and `adversarial-review.md` ("Start only when every check has finished and passed on that head" is there; the `NOT STARTED` hand-back landed by pitboss#48); stays: `check.yml`, `guidelines.py`, `qsweep`'s `WAIT-FOR-CI`, the `text-lint` status |
| 986 | Quarantine a p0 test with its ticket, a race fix shows cause, injection and CI run, no fixed waits in e2e (#976) | `e2e.md` adds section "Quarantine and race fixes" (split; 1023 is stacked on it); `agents/worker.md`, `agents/reviewer.md` and `orchestration.md` "Briefs and the machine" (split) | shrinks: the section moves to `engineering.md`, and the race lines of the agents and the briefs section move to `rules.md`, "Reviews" and `engineering.md` (root cause from the captured evidence, an injection that forces the losing order, no repeat to count failures); stays: `guidelines.py` and its test, and the `Quarantine:` / `Race:` lines (`test.fixme`, "on every project") |
| 982 | A tracked pre-push hook runs CI's first-minute checks and refuses the push when one fails | `ci.md` checking locally and new "pre-push" section (split); `agents/worker.md` "Where you work" bullet, `skills/sweep/SKILL.md` and `skills/sweep/qsweep` (rows split, quire, split) | stays: `.githooks/pre-push`, `scripts/pre-push.py`, `qsweep` (`HOOKS-NOT-INSTALLED`, `NO-VERIFY`, the env file), and the `core.hooksPath` clause of the `worker.md` bullet (the rest of that bullet, a worktree of your own, is already in `rules.md` and is not changed) |
| 981 | The static groups take the app that build checked and need build (#974) | `ci.md` compiler's cache (split) | stays: bats build cache |
| 970 | The monitor does not take a stop of the whole machine for a watchdog gone quiet (#908) | `e2e.md` flight recorder (split) | stays: the watchdog |
| 969 | The e2e job gets its Japanese font from pwa's e2e-setup, not from apt (#932) | `e2e.md` tool list of "A worker's machine matches CI" (split) | stays: the list of tools |

Open PRs that change no row of `pitboss` or `split`, so are not listed above: 1032
(`book-text.md`, quire), 1022 (`epub-media.md`, quire), 980 (`platform.md`, quire), 1020,
1003 (workflows only), 1005 (`e2e/helpers.js` only). PR 971 was in the first list and merged on
2026-10-29, so 24 are open now. The PRs that change `.claude/orchestration.md`,
`.claude/agents/` or `.claude/skills/` are 1023, 1021, 1017, 1013, 991, 986 and 982; the
`docs/quire-inventory-evidence.sh` prints the file list of each.
