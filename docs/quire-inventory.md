# Inventory of bats-lang/quire's rules: what is pitboss's, what is quire's

Ticket: dev-skill-up/pitboss#41. Source: bats-lang/quire `main` at the time of writing
(`CLAUDE.md` and the 20 files of `.claude/rules/`), and the 25 open quire pull requests.
No file is moved by this ticket; each move is a ticket of its own, filed from this list.

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
the quire text shrinks to a pointer.

## quire's CLAUDE.md, by section (13 sections)

| # | Section | Verdict | Lands in, or why it stays |
|---|---|---|---|
| 1 | Decisions are made by research, not left to the human | pitboss | `rules.md`, "How decisions are made" (already holds the first rule; the rest of the section is added there) |
| 2 | A proof is a proof | split | Moves: the first paragraph (a requirement that says proof means a static proof) and "a claim that is only tested is said to be tested, and the proof is still owed", to `engineering.md`. Stays: the paragraph on trusted primitives, `praxi`, `assume`, `$UNSAFE` and the array package (ATS2 proofs) |
| 3 | Comments name their area by keyword | pitboss | `engineering.md` |
| 4 | Names are words | split | Moves: the rule that names are words and that terse names collide, and the loop-index exception, to `engineering.md`. Stays: the examples about element ids and numbered-id prefixes of 16 bytes (quire's DOM ids) |
| 5 | Priorities | split | Moves: p0 to p3 and "Order of work" (worker in progress, open PR, merge, then tickets, blocked tickets, no downgrades without the owner) to `rules.md`, "Agents and slots" and "Tickets" (largely there already). Stays: the paragraph "The Android release is not a priority" (Android release) |
| 6 | Pipeline and tooling improvements belong in bats or pwa | split | Moves: "We do not write shell scripts (or any non-bats code of our own) unless all other avenues are exhausted" (as "our own language, not shell") and "No mtimes in freshness", to `engineering.md` and `ci.md`. Stays: the first two paragraphs (what belongs to bats and to pwa, quire#623, #635, #637, #646, #731) |
| 7 | Breaking changes keep at least one published version of overlap (#762) | split | Moves: the whole rule to `rules.md`, "Published APIs" (already there word for word; delete the copy). Stays: the sentences naming `.claude/orchestration.md` and `tests/static/guidelines.py` |
| 8 | CI is pinned | split | Moves: every input pinned in the source, a committed lock, CI never relocks, pins move only through a reviewed PR, the daily relock, no bot opens PRs, to `ci.md`. Stays: the names (`bats.lock`, `.github/bats-version`, `android.yml@<sha>`, Dependabot grouping, #996, the setup action) |
| 9 | No cache key is relied on for correctness (#622) | split | Moves: the first sentence (a restored cache is judged by the tool, never by the key that found it) to `ci.md`. Stays: the bats stamp, the memo and the key format `quire-<name>@<commit>` |
| 10 | Check locally before every push | split | Moves: check locally before a push, a run over a population is a random sample with a printed seed and the PR says the sample and why it suffices, the checkout stays, to `ci.md` and `rules.md`, "Checkouts and disk". Stays: `bats check`, 10 to 15 minutes cold, `qsweep clean`, the compiler setup |
| 11 | Evidence, red tests and CI | split | Moves: evidence for every claim in the PR body, a red test is root-caused, "it passed again" is not a cause, the author owns CI until green, a reviewer starts only on a green exact head, to `rules.md`, "Reviews" and "Briefs and workers" (largely there already). Stays: the last sentence naming `.claude/agents/*.md`, `orchestration.md` and `tests/static/guidelines.py` |
| 12 | The version is the commit's | split | Moves: a version is the commit's, never the build's, so one commit always gives one version, to `engineering.md`. Stays: the pointer to `.claude/rules/release.md` |
| 13 | Play release | quire | Google Play and `check.yml`'s `play-internal` job |

## quire's `.claude/rules/`, by file (20 files)

| File | Verdict | Lands in, or why it stays |
|---|---|---|
| `backup-errors.md` | split | Moves: the rule of "Every error says what to do (#360)" (a failure is said with a next step, the unexpected is its own outcome) to `engineering.md`. Stays: the banner, `notice.bats`, Reopen Quire, Copy details, the backup section (#362), the protected book section (#427) |
| `backup-write-answer.md` | quire | Android Auto Backup file and bridge's `backup_write_answer` |
| `book-memory.md` | quire | Quire's page arenas and EPUB pathological structure |
| `book-text.md` | quire | Encodings, series and CSS sizes of EPUB text |
| `cfi.md` | quire | EPUB CFI |
| `ci.md` | split | Moves: "Only the groups a change can affect run" draft bullet (a draft PR runs no costly job) and "A run over a population is a sample" bullet of "Checking locally before a push", to `ci.md`. Stays: every other section: pins and relock names, the Android lock, the compiler's cache (bats stamp), static fixtures, solver fixtures, the merge queue (this repository's runner pool and 60 minute window), Node's packages, the mutation check (ATS2 proofs), the `plan` job's table, the local commands, the flight recorder on a local machine |
| `dictionaries-catalogues.md` | quire | StarDict dictionaries and OPDS catalogues |
| `e2e.md` | split | Moves: the bullet "A test never waits in real time for a moment of the app's own" of "No flaky waits", the first paragraph of "A worker's machine matches CI (#713)" ("This machine lacks X is never a reason for a spec to be skipped"), to `engineering.md` and `rules.md`, "Briefs and workers". Stays: projects and groups, `clickControl`, `rawMouse`, the Playwright pin, the tool list, two books, the stall watch, the flight recorder (Playwright, Chromium and the kernel's tracefs) |
| `epub-format.md` | quire | EPUB archive, spine and package rules |
| `epub-media.md` | quire | EPUB narration, media, fonts and MathML |
| `interface.md` | split | Moves: "Failures are said, never dropped" (the rule, not the `notice.bats` names) to `engineering.md`. Stays: the stylesheet under proofs, `ui.bats`, "Nothing is lost at a click" (reader Undo and Trash), overlays and Back |
| `library-records.md` | quire | Quire's stored records, codec and Replace |
| `library-screen.md` | quire | The library screen |
| `platform.md` | quire | Quire's use of bridge's platform atoms |
| `reader-layout.md` | quire | Reader gestures, spreads and writing modes |
| `reader.md` | quire | Reader notes, positions and touch selection |
| `release.md` | split | Moves: the first sentence of "The version is the commit's" (the date of the commit, never of the build) to `engineering.md`. Stays: the rest (`YEAR.MONTH.DAY.SECONDS`, `bats_commit_*` facts, `versionName`, `versionCode`) and "Main goes to Play's internal testing" (Google Play) |
| `sync.md` | split | Moves: the rule of "Every outcome is said, and the unexpected as such (#334)" (an error is an outcome of its own, never folded into another, and what is not recognised is explicit) to `engineering.md`. Stays: the sync file, the services, the 30 second answer, Google, Dropbox and Nextcloud |
| `types.md` | split | Moves: "A choice is a datatype" rule (an int never encodes one of a fixed set of cases; "none" is an option, not -1) to `engineering.md`. Stays: "What allocates is linear" (wasm, ATS2 `datavtype`, `lincloptr1`) and the `case+` lint name |
| `vocabulary.md` | quire | The words-looked-up feature and its KOReader schedule |

Count: 20 files: 0 `pitboss`, 7 `split` (`backup-errors`, `ci`, `e2e`, `interface`, `release`,
`sync`, `types`) and 13 `quire` (`backup-write-answer`, `book-memory`, `book-text`, `cfi`,
`dictionaries-catalogues`, `epub-format`, `epub-media`, `library-records`, `library-screen`,
`platform`, `reader-layout`, `reader`, `vocabulary`). CLAUDE.md: 13 sections: 2 `pitboss`
(rows 1 and 3), 10 `split` and 1 `quire` (row 13).

## Open quire pull requests that change a `pitboss` or `split` file or section

Verdict words: closes (all its changes are moved content), shrinks (names what stays), stays
(it changes only text that stays in quire). No open PR closes: each also changes code, a
workflow, a fixture or text that stays.

| PR | Title | Changes (verdict row) | Result |
|---|---|---|---|
| 1035 | The Android version code is the commit count plus an offset | `release.md` (split) | stays: the version code is `versionCode` and Play, which stay |
| 1034 | Reject fixtures name the one constructor they are about, and a lint refuses an expect that lists more (#984) | `ci.md` static fixtures (split) | stays: bats fixtures |
| 1031 | Place the selection toolbar outside the Android floating menu's band | `e2e.md` projects and groups (split) | stays: Playwright projects |
| 1023 | Replace the fixed waits of e2e/ with waits for an event (#985) | `e2e.md` new section "Quarantine and race fixes" (split) | shrinks: the section moves to `engineering.md`; stays: `e2e/*.js` helpers, `stall-capture.spec.js`, `guidelines.py` |
| 1018 | A capture reads a snapshot of the kernel ring and never stops it (#910) | `e2e.md` flight recorder (split) | stays: kernel tracefs |
| 1017 | Short jobs run locally, CI runs the rest; briefs may not run in the background or sleep (#911) | `CLAUDE.md` section 10, `ci.md` checking locally (split) | shrinks: the rule on short jobs moves to `ci.md` and `rules.md`; stays: `worker.md`, `guidelines.py`, `phrases.tsv`, the fixture |
| 1015 | ci.md: why a merge-queue entry is removed (#1026) | `ci.md` merge queue (split) | stays: this repository's merge queue |
| 1009 | e2e: a failed test keeps its trace, screenshot, DOM and console, and the job summary names them (#1008) | `e2e.md` (split) | stays: Playwright capture |
| 1007 | scripts/ci-groups.py local lists the fixtures a change affects (#1006) | `ci.md` checking locally (split) | stays: `ci-groups.py` and bats#570 |
| 997 | A watchdog report keeps the whole ring and says where it begins (#993) | `e2e.md` flight recorder (split) | stays: kernel ring |
| 991 | A draft runs plan and build; a head with no completed check run is not approved (#978) | `CLAUDE.md` section 11, `ci.md` draft bullet (split) | shrinks: "a head with no completed run is never approved" and the draft rule move to `rules.md` and `ci.md`; stays: `check.yml`, `guidelines.py`, `reviewer.md` |
| 986 | Quarantine a p0 test with its ticket, a race fix shows cause, injection and CI run, no fixed waits in e2e (#976) | `e2e.md` new section "Quarantine and race fixes" (split) | shrinks: the section moves to `engineering.md`; stays: `guidelines.py` and its test |
| 982 | A tracked pre-push hook runs CI's first-minute checks and refuses the push when one fails | `ci.md` checking locally and new "pre-push" section (split) | stays: `.githooks/pre-push`, `scripts/pre-push.py`, `qsweep` |
| 981 | The static groups take the app that build checked and need build (#974) | `ci.md` compiler's cache (split) | stays: bats build cache |
| 971 | The host-stall record names what the machine was doing (#909) | `e2e.md` flight recorder (split) | stays: the watchdog |
| 970 | The monitor does not take a stop of the whole machine for a watchdog gone quiet (#908) | `e2e.md` flight recorder (split) | stays: the watchdog |
| 969 | The e2e job gets its Japanese font from pwa's e2e-setup, not from apt (#932) | `e2e.md` tool list of "A worker's machine matches CI" (split) | stays: the list of tools |

Open PRs that change no row of `pitboss` or `split`, so are not listed above: 1032
(`book-text.md`, quire), 1022 (`epub-media.md`, quire), 980 (`platform.md`, quire), 1020,
1003 (workflows only), 1005 (`e2e/helpers.js` only), 1021 and 1013 (`.claude/orchestration.md`
and `.claude/skills/sweep`, which are not rows of this inventory).
