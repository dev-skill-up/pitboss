"""The sentences of the briefs about a new or loosened lint (pitboss#180).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

LINT_TEST = (
    "Lint tests: a lint, check or exemption that is new or loosened ships a test"
    " for the nearest input it must still reject (a form spelled the way the"
    " loosened rule now accepts, such as a fixed sleep whose timer handle is"
    " kept), as well as a test for the input it accepts."
)
LINT_TEST_REVIEW = (
    "Lint tests: a lint, check or exemption that is new or loosened and ships no"
    " test for the nearest input it must still reject is changes needed (a form"
    " spelled the way the loosened rule now accepts, such as a fixed sleep whose"
    " timer handle is kept); a test of the accepted input alone does not show"
    " that the rule still rejects."
)
