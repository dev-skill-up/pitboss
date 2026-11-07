"""The separate-agent sentence of the relock review brief (pitboss#34).

A relock is reviewed because its pins-check did not print ``OK``, and its
reviewer runs that command (keyword: pins-only). Like those of ``brieftext``,
it is pinned by tests, so a change to it is a reviewed code change.
"""

SEPARATE_PINS = (
    "Separate agent: you are not the author; if you wrote any part of the change,"
    " say so and stop. You run nothing but the project's pins-check command:"
    " you read the diff and the CI of the head."
)
