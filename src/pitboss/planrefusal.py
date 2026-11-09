"""The open tickets and PRs that a refused Plan check names (pitboss#388).

A PR whose newest trusted ``Plan check`` comment says ``Plan check: refused``
waits for every open ticket or PR that comment names, as pitboss#372 was refused
until pitboss#373 landed: it is offered no step, and the sweep prints ``BLOCKED``
in place of one (keyword: plan-refusal, blocked-pull). A newer ``Plan check: ok``
comment ends the wait, and so does the close or the merge of what it names.
"""

from typing import AbstractSet, Sequence

from . import blockers, config, ghapi, sessionurl, steps, ticketblock

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


def _is_open(github: ghapi.GitHub, reference: str) -> bool:
    return blockers.open_ticket(github, reference) is not None


def open_blockers(
    github: ghapi.GitHub,
    trusted: AbstractSet[str],
    pull: str,
    ticket: str,
) -> Sequence[str]:
    """The open tickets and PRs that the refusal of a PR names.

    Args:
        github: the API.
        trusted: the author associations whose comments count.
        pull: the PR, ``owner/name#number``, which never blocks itself.
        ticket: the ticket it fixes, which never blocks it either.

    Returns:
        The references, each once, in the order of the comment.
    """
    text = refusing(ticketblock.comments_of(github, pull, trusted))
    names = blockers.named(text, config.repo_of(pull)) if text else []
    wanted = dict.fromkeys(each for each in names if each not in {pull, ticket})
    return [each for each in wanted if _is_open(github, each)]
