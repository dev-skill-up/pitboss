# Engineering rulings

These are the owner's rulings on code, tests and errors. They hold in any
language, so they are not one project's: the project's own tools, paths and
ticket numbers stay in that project's notes. Read this file with `rules.md`
before briefing or reviewing a worker whose change touches code.

## A proof is a proof

When a requirement says proof, it means a static proof, checked by the
compiler from types and lemmas. It never means a test, a runtime check, a
read-back, an assertion or a witness that is only believed. A claim that is
only tested is said to be tested, and the proof is still owed: where the proof
system cannot reach (a library had no model of an array's contents), the tool
is extended (a content-indexed array API in that library), not worked around
at runtime.

## Comments name their area by keyword

A comment states its reason in one line and names the area by keyword; the
detail lives in the project's notes (its rules files): search them for the
keyword before changing the code.

## Names are words

Element ids, numbered-id prefixes, variables, static indices and functions are
named by what they are, in words: `search-close`, `toc-row12`, `query`,
`query_len`, not `qsrz`, `qe`, `q`, `qn`. Nothing is short of bytes, and terse
names collide (a rename of the id `qn` once also hit a query length of the
same name). A loop index (`i`, `j`) or a conventional pair (`l` and `n` for an
array's location and size) may stay short within a few lines.

## Our own code is in our own language, not shell

**We do not write shell scripts (or any code outside the project's own
language) unless all other avenues are exhausted.** We self-host in the
project's language, implement in it, build tooling in it; dependencies on
other tools are fine; only what is impossible in it (like getting it to run)
is not written in it. Our own code is in the project's language; the only
other code is what is impossible there, a dependency's own format, or a
third-party tool used as it is. A workflow `run:` step that does more than
call one subcommand of the project's tool or one third-party tool is code we
wrote. A PR that adds code of ours outside the project's language names the
avenue it exhausted, and the reviewer rejects it without that.

**No mtimes in freshness.** Nothing that decides whether an output is fresh (a
build, a cache, a memo, a test selection) reads a file's time: it compares
content hashes.

## A choice is a datatype

An int never encodes one of a fixed set of cases: a choice is a datatype
matched exhaustively, so a case left out does not type-check, and "none" is an
option, not -1. Ints are quantities, offsets and indexes.

## Failures and outcomes are said

One entry for three rulings, all of one rule: a failure is said, with what to
do next, and an unexpected one is said as such.

- **Every error says what to do.** A failure is said with a next step, made in
  one place from data. The words come from total matches (one for what
  failed, one for the step to take), so a failure added without words or
  without a next step does not type-check.
- **Every outcome is said, and the unexpected as such.** A platform or library
  reports every error and unexpected condition as an outcome of its own, never
  folded into another (an error that ended a consent screen once reached the
  app as the user backing out). What it does not recognise is an explicit
  `Unexpected` constructor carrying the case and the answer as the platform
  wrote it. The app matches every answer exhaustively and handles every
  constructor visibly.
- **Failures are said, never dropped.** What fails is said. A write of the
  user's own data is checked, and a failure says once a session that storage
  may be full; a screen that cannot be shown leaves the user on the one they
  were on, or, if it was the first, back at the start. A copy is confirmed by
  its own status, apart from an undo toast.

## A test never waits in real time for a moment of the app's own

A back button's ten seconds, a toast's two seconds, a polling interval: a test
never waits in real time for such a moment. It installs the fake clock before
the page opens and runs the clock to the moment: the thing is asserted to be
there shortly before the moment's end and gone shortly after, and a clock run
on in steps waits for an answer that comes in real time. Real time stays for
the time-measuring budgets, the stall watch, media playback and anything that
waits for a font or the network.

## A version is the commit's, never the build's

A project's version is the date of the commit it is built from, never of the
build, so the same commit always gives the same version.
