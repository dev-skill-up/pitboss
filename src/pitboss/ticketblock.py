"""The open ticket or PR that a ticket says it cannot be worked on until (pitboss#163).

A ticket states in its body or in a comment ``Cannot be worked on until
<owner/repo#n> has merged``, ``Blocked by <owner/repo#n>``, ``Blocked on
<owner/repo#n>`` or ``Depends on <owner/repo#n>`` (any case; a bare ``#n`` is of
the ticket's repository; pitboss#280). While that ticket or PR is open the
ticket is not work that can
be started, so ``slots next`` and the sweep print ``BLOCKED <ticket> by
<owner/repo#n>`` for it and no ``NEXT`` line, and the blocker is offered ahead
of it (``dependency``; keyword ticket-blocked). When the blocker closes or
merges the ticket is listed again with no other change. A tracking ticket whose
newest comment says it ``closes when #a, #b and #c have merged`` is blocked by
each of them that is open (keyword: closes-when, pitboss#388), and a PR is
blocked by the open blockers of the ticket it fixes (keyword: blocked-pull).
"""

import re
from typing import AbstractSet, Callable, Sequence

from . import blockedform, config, ghapi, ledger, parsing

# keyword: closes-when (pitboss#388): a status comment of a tracking ticket
CLOSING = re.compile(
    r"(?i)closes\s+when\s+([^.;]+?)\s+(?:(?:have|has|are|is)\s+)?(?:been\s+)?"
    r"merg(?:e|es|ed)\b"
)
TOKEN = re.compile(r"(?:[\w.-]+/)?[\w.-]*#\d+")


def closing(text: str, repo: config.Repo) -> Sequence[str]:
    """The tickets a status comment says it closes when they have merged.

    A bare ``#n`` in the list is of the repository the comment names that
    number in, in full, elsewhere (a status comment that wrote
    ``owner/lib#94`` and later ``closes when #94 has merged``), else of the
    ticket's own repository.

    Args:
        text: a comment of a ticket.
        repo: the repository of a bare ``#n`` that no full one explains.

    Returns:
        The references as ``owner/name#number``, in the order of the list.
    """
    found = CLOSING.search(text)
    if found is None:
        return []
    qualified = (ledger.reference(each, repo) for each in TOKEN.findall(text))
    where = {
        each.rpartition("#")[2]: each.rpartition("#")[0]
        for each in qualified
        if each.rpartition("#")[0] != repo.slug
    }

    def spelled(token: str) -> str:
        number = token.rpartition("#")[2]
        if token.startswith("#") and number in where:
            return f"{where[number]}#{number}"
        return ledger.reference(token, repo)

    return [spelled(each) for each in TOKEN.findall(found.group(1))]


def comments_of(
    github: ghapi.GitHub, reference: str, trusted: AbstractSet[str]
) -> Sequence[str]:
    """The comments of a ticket that trusted authors wrote.

    Args:
        github: the API.
        reference: the ticket, ``owner/name#number``.
        trusted: the author associations whose comments count.

    Returns:
        The comments' texts.
    """
    path = "repos/" + reference.replace("#", "/issues/") + "/comments"
    posted = ghapi.pages(github, path, parsing.comments)
    return [each.body for each in posted if each.author_association in trusted]


def open_blockers(
    repo: config.Repo,
    found: Sequence[str],
    is_open: Callable[[str], bool],
    own: AbstractSet[str] = frozenset(),
) -> Sequence[str]:
    """Every blocker that is still open (keyword: closes-when, pitboss#388).

    The sentences of ``named`` count in the body and in every comment; the
    ``closes when ... merge`` sentence counts only in the newest text of
    ``found`` (a status comment is replaced by the next one).

    Args:
        repo: the repository of a bare ``#n``.
        found: the texts of the ticket: its body, then its comments, oldest first.
        is_open: whether a ticket or PR, as ``owner/name#number``, is open
            (False when it cannot be read).
        own: references that never block: the ticket itself and the PR that
            fixes it.

    Returns:
        The open blockers as ``owner/name#number``, each once, in the order
        the texts name them.
    """
    newest = found[-1:] if len(found) > 1 else []
    every = [each for text in found for each in blockedform.named(text, repo.slug)]
    every += [each for text in newest for each in closing(text, repo)]
    distinct = dict.fromkeys(each for each in every if each not in own)
    return [each for each in distinct if is_open(each)]
