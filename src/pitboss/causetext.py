"""The rule about the cause of a red check (keyword: red-cause, pitboss#420).

The sweep's CAUSE line and the brief that fixes a red CI print it, so a change to
it is a reviewed code change and the tests pin it.
"""

RULE = (
    "the answer to a red check is its cause: either the log names it (the step,"
    " the line) or the next change is the trace or state capture that would show"
    " it (a ticket or a change of its own); a push or a re-run whose only purpose"
    " is a new run is refused"
)
