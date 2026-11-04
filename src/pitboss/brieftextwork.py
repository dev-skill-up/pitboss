"""The sentences of a worker brief about how to wait on the checks (pitboss#175).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

NOX_ORDER = (
    "Nox order: where the checks are nox sessions, run `nox -r -s tests-3.13`"
    " (one session) first and fix until it passes; only then run the other"
    " sessions (`lint`, `mypy`, `skills`), with `-r`. Never invoke `virtue` or"
    " `python -m virtue` by hand: the nox session is the way to run tests. Start"
    " nothing in the background that needs polling: use one foreground command"
    " under `timeout 598`, or one `Monitor` with an `until` loop."
)
FIRST_DESIGN = (
    "First design: throwing away a first design is acceptable and is not a thing"
    " to avoid; rewrite it when the tests show it is wrong."
)
SENTENCES = (NOX_ORDER, FIRST_DESIGN)
