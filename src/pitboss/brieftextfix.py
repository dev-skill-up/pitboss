"""The sentences of the fix round and of an Execution fixed after a ruling.

Like those of ``brieftext``, they are pinned by tests (keyword: fix-round-kind,
ruling-first, pitboss#390).
"""

RULING_NAMED = (
    "Ruling: the Opus ruling at {ruling} came first; do what it rules for the"
    " Execution and nothing else."
)
TASK_FIX_ROUND = (
    "Task: PR {reference}: fix the findings of {review}{quoted}, each one, and"
    " nothing else: make no change that no finding names. A finding may name a"
    " code, doc or test change, and the Plan may change to match it. Merge"
    " origin/{base} into the branch (never rebase, never force-push), run"
    " `pitboss nox` once on the result, build the Evidence again with `uvx"
    " pitboss expand`, run `uvx pitboss plan-check <body file>` and post its whole"
    " output as a PR comment, and patch the `Head:` line."
)
