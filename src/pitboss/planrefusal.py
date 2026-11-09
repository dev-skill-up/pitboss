"""The refusal of a Plan check, which blocks a PR on what it names (pitboss#388).

A PR whose newest trusted ``Plan check`` comment says ``Plan check: refused``
waits for every open ticket or PR that comment names, as pitboss#372 was refused
until pitboss#373 landed: it is offered no step, and the sweep prints ``BLOCKED``
in place of one (keyword: plan-refusal, blocked-pull). A newer ``Plan check: ok``
comment ends the wait, and so does the close or the merge of what it names.
"""

from typing import Sequence

from . import sessionurl, steps

REFUSED = "Plan check: refused"


def _checks(texts: Sequence[str]) -> Sequence[Sequence[str]]:
    # the comments whose first line is ``Plan check``, as lines
    found = [sessionurl.lines(each) for each in texts]
    first = steps.PLAN_CHECK_FIRST_LINE
    return [each for each in found if each and each[0].rstrip() == first]


def refusing(texts: Sequence[str]) -> str:
    """The text of the newest ``Plan check`` comment, when it refuses the Plan.

    Args:
        texts: the trusted comments of a PR, oldest first.

    Returns:
        The comment's text, or "" when there is none or the newest one is not a
        refusal.
    """
    checks = _checks(texts)
    newest = checks[-1] if checks else []
    refused = any(each.startswith(REFUSED) for each in newest)
    return "\n".join(newest) if refused else ""
