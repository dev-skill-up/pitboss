"""The sentences of a worker brief about how to wait on the checks (pitboss#175).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

NOX = (
    "Nox: where the checks are nox sessions, run `timeout 598 pitboss nox` after"
    " every edit and before every push, for iterating too (the tests of one Python"
    " version first, then the skills, lint and mypy; it stops at the first failure"
    " and always uses `-r`); a targeted test module, `nox -s ...` or `virtue` is"
    " never run by hand, and never the full `nox -r`: CI's `Run Nox` step runs the"
    " whole suite."
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
DEVIATIONS = (
    "Deviations: the hand-back, and the PR body, have a `Deviations:` line naming"
    " each rule of this brief you broke (an edit by `sed`, a heredoc or `rm`"
    " instead of the Edit tool included), or `none`; it is part of the form of"
    " the hand-back, and a hand-back without it is NOT STARTED and is sent back"
    " (pitboss#257)."
)
SENTENCES = (NOX, NOX_ORDER, FIRST_DESIGN, DEVIATIONS)
