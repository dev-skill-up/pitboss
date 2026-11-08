"""The sentence of the review briefs about hidden failures (pitboss#353).

Like those of ``brieftext``, it is pinned by tests, so a change to it is a
reviewed code change.
"""

FAILURE_REVIEW = (
    "Failures: a change that turns a failing condition (a rejected credential, a"
    " missing input, an error exit) into a green run, a skip, a notice, a warning"
    " or a default is changes needed, whatever the ticket's Done-when allows,"
    " unless the owner's own words quoted in the ticket ask for it."
)
