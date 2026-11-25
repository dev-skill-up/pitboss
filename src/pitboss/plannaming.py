"""A Plan that names the head is the same Plan at the next head (plan-names-head)."""

from . import expansion


def current(recorded: str, now: str, reviewed: str, head: str) -> bool:
    """Whether a Plan digest recorded at a head is current at another head.

    A Plan whose evidence names the head (``commits/<head>/status``) changes
    with every push, as a ``Head:`` line does and a run's id does (keyword:
    plan-names-head, quire#1125): the push is not an edit of the Plan.

    Args:
        recorded: the digest the review records, empty when it records none.
        now: the Plan section now, empty when the body has none.
        reviewed: the head the review read (possibly abbreviated).
        head: the head now.

    Returns:
        True when ``expansion.current_for`` the Plan holds, or the head moved
        since the review and the Plan section names the head it has now: with
        the reviewed head put back where it names the head, it is the Plan the
        review read (a review that kept only some digits of its head cannot
        be rebuilt, and the Plan naming the head passes).
    """
    subject = expansion.Subject
    if expansion.current_for(subject.PLAN, recorded, now):
        return True
    moved = not expansion.current_for(subject.HEAD, reviewed, head)
    if not (moved and head and head in now):
        return False
    return _rebuilt(recorded, now, reviewed, head)


def _rebuilt(recorded: str, now: str, reviewed: str, head: str) -> bool:
    # the review's full head put back where the Plan names the head: the same words
    if len(reviewed) != len(head):
        return True
    return expansion.current_for(
        expansion.Subject.PLAN, recorded, now.replace(head, reviewed)
    )
