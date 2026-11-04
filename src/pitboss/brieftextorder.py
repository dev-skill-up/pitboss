"""The sentences of the briefs about a change of a precedence order (pitboss#182).

Like those of ``brieftext``, they are pinned by tests, so a change to them is a
reviewed code change.
"""

ORDER_TICKET = (
    "Order tables: a ticket or ruling that changes the order in which steps are"
    " offered gives, in its Done-when, a table of the full order (every state"
    " against the step offered) and names a test per row, so that no state is"
    " left to the worker's choice."
)
ORDER_REVIEW = (
    "Order tables: a PR that changes the order in which steps are offered is"
    " changes needed when a doc row (`sweep.md`, `rules.md`, `slots.md`) or the"
    " code differs from the ticket's table of the full order, or when a row of"
    " that table has no named test."
)
