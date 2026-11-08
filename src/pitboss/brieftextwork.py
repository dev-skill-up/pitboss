"""The sentences of a worker brief about how to wait on the checks (pitboss#175).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

NOX = (
    "Nox: where the checks are nox sessions, run `timeout 598 pitboss nox` before"
    " each push and when you need feedback, once for a head (the skills, lint and"
    " mypy first, then the tests of one Python version, which stop at the first"
    " failing test; it stops at the first failing session and always uses `-r`); a"
    " targeted test module, `nox -s ...` or `virtue` is never run by hand,"
    " and never the full `nox -r`: CI's `Run Nox` step runs the whole suite."
)
NOX_ORDER = (
    "Nox order: where the checks are nox sessions, never invoke `virtue` or"
    " `python -m virtue` by hand: the nox session is the way to run tests. Start"
    " nothing in the background that needs polling: use one foreground command"
    " under `timeout 598`, or one `Monitor` with an `until` loop."
)
FIRST_DESIGN = (
    "First design: throwing away a first design is acceptable and is not a thing"
    " to avoid; rewrite it when the tests show it is wrong."
)
TASK_RUN_PLAN = (
    "Task: PR {reference}: its Plan was approved alone (a review with a `Plan:` line"
    " and no `Execution:` line), after an Opus ruling, so its commands were never"
    " run. Run each precise command of the Plan as written, and fill the Execution"
    " and Evidence of the PR body with what they printed. The Plan is approved: do"
    " not change it (pitboss#201)."
)
TASK_ADD_CI_QUOTES = (
    "Task: PR {reference} is ready and its checks passed, and its Plan has CI-quote"
    " rows the body does not answer yet. Add each quote to the Execution as a line"
    " that starts `CI quote:` and points to the run (the workflow, the job URL of"
    " the head, the step and a greppable string that step prints), as the CI"
    " pointer rule says; paste no log output. Change nothing else; the Plan is"
    " approved (pitboss#277)."
)
DEVIATIONS = (
    "Deviations: the hand-back, and the PR body, have a `Deviations:` line naming"
    " only what costs something: `pitboss nox` run more than once on one head"
    " (`--all` is not feedback), a required step you skipped, or a rule of the"
    " owner's you broke; a heredoc instead of the Edit tool, a virtualenv, a"
    " redirected output file or a research fetch is no deviation, and the line"
    " is `Deviations: none` beside them; it is part of the form of the"
    " hand-back, and a hand-back without it is NOT STARTED and is sent back"
    " (pitboss#257, pitboss#345)."
)
TEMP_RUNS = (
    "Temp files: a check that runs more than once gets its own `TMPDIR`, removed"
    " right after each run; a run that needs more than 1 GiB is left to CI"
    " (pitboss#288)."
)
DEPENDENCY = (
    "Dependency: a ticket that depends on another open ticket is not impossible in"
    " one PR and is never ground for a split (owner, 2026-11-06): if you hand back"
    " NOT STARTED for it, name the ticket it waits for; the orchestrator does that"
    " ticket first, and adds a repository the mission needs (add_repo) without"
    " asking (pitboss#280)."
)
SENTENCES = (NOX, NOX_ORDER, FIRST_DESIGN, DEVIATIONS, TEMP_RUNS, DEPENDENCY)
