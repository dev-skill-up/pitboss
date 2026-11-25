"""A PR as read, for the witnesses and the tests of the decider (keyword: witnesses).

``decide.facts_of`` runs the review flow on what was read, so a record holds the
flow's inputs: a state whose step is the flow's.
"""

from . import flowstate, pullfacts, pullobject, reviews, totalschema

# the PR object a gate reads when it reads none
NO_OBJECT = pullobject.pull_object({}, totalschema.schema())
NO_SOURCES = reviews.Sources(comments=(), reviews=())


def read_of(
    facts: pullfacts.PullFacts, state: flowstate.PullState
) -> pullfacts.PullRead:
    """A PR as read: its facts, less the step, and the flow's state.

    Args:
        facts: what a test says of the PR (its step is not read).
        state: what the review flow's rows ask of it.

    Returns:
        The PR as read.
    """
    return pullfacts.PullRead(
        repo=facts.repo,
        pull=facts.pull,
        checks=facts.checks,
        review=facts.review,
        standing=facts.standing,
        signals=facts.signals,
        unreadable=facts.unreadable,
        review_rounds=facts.review_rounds,
        state=state,
        posted=pullfacts.Posted(object=NO_OBJECT, statuses=(), sources=NO_SOURCES),
    )
