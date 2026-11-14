"""The decision on an act verb, from what the one read gave (keyword: act-verbs).

``decide`` makes it and ``act`` looks it up (``gateverbs.lookup``): an owner message
with no disposition, a hold that covers the verb, then the fact the verb's own
decision turns on. The first that stands is ``NotDone``; when none stands the verb
is None. Each row is a field of ``Rows``, so a test can take one out.
"""

import dataclasses
from typing import Callable, Sequence, assert_never

from . import actfacts, actport, answer, holdparse, ticketreader

UNGATED = frozenset({"ack", "clean"})  # what the owner and the holds never stop
DEFAULT_BRANCHES = frozenset({"main", "master"})  # a push goes to a PR's branch
RowRule = Callable[[actfacts.ActRead, holdparse.Held], Sequence[answer.NotDone]]


def owner_row(read: actfacts.ActRead, held: holdparse.Held) -> Sequence[answer.NotDone]:
    """What stands while an owner message has no disposition.

    Args:
        read: what the verb is decided from.
        held: each repository's holds.

    Returns:
        One for each such message, in order.
    """
    return [
        answer.NotDone(
            why=answer.Why.OWNER_MESSAGE,
            line=f"owner message {each} has no disposition: `pitboss act ack"
            f" {each} --kind hold|cap|ruling|none`",
        )
        for each in read.pending
    ]


def hold_row(read: actfacts.ActRead, held: holdparse.Held) -> Sequence[answer.NotDone]:
    """What stands when a hold covers the verb.

    Args:
        read: what the verb is decided from.
        held: each repository's holds.

    Returns:
        One for each hold that covers it, in order.
    """
    if read.verb in actport.ENDS_A_HOLD:
        return []
    return [
        answer.NotDone(
            why=answer.Why.HOLD, line=f"hold: {hold.title} holds {read.verb} in {repo}"
        )
        for repo in read.repos
        for hold in held.get(repo, ())
        if holdparse.covers(hold, read.verb)
    ]


def _check(check: actfacts.Check) -> Sequence[answer.NotDone]:
    # the one fact a verb's decision turns on
    match check:
        case actfacts.Size():
            return _size(check)
        case actfacts.Starters():
            return _started(check)
        case actfacts.Authored():
            return _authored(check)
        case actfacts.TicketForm():
            return _form(check.read)
        case actfacts.Pushing():
            return [*_pushed_to(check), *_branch(check), *_prepush(check)][:1]
        case actfacts.Worktree():
            return _worktree(check)
        case _:  # pragma: no cover
            assert_never(check)


def _not_done(why: answer.Why, line: str) -> Sequence[answer.NotDone]:
    return [answer.NotDone(why=why, line=line)]


def _size(check: actfacts.Size) -> Sequence[answer.NotDone]:
    if check.lines <= check.p90 or check.ruled:
        return []
    line = f"Max-lines {check.lines} is over {check.repo}'s p90 {check.p90}"
    return _not_done(answer.Why.OVER_P90, line + ": a ruling names it")


def _started(check: actfacts.Starters) -> Sequence[answer.NotDone]:
    if not check.pulls:
        return []
    line = f"PR #{check.pulls[0]} closes {check.ticket}, so a worker started:"
    line += " a started ticket gets nothing added (file a new ticket)"
    return _not_done(answer.Why.STARTED, line)


def _authored(check: actfacts.Authored) -> Sequence[answer.NotDone]:
    if not check.ours:
        return _not_done(answer.Why.NOT_OURS, "not a comment pitboss act posted")
    if check.keyed:
        line = f"a line starts with a review or act key: {check.keyed[:40]!r}"
        return _not_done(answer.Why.NOT_OURS, f"{line}; use the verb")
    return []


def _form(read: ticketreader.Read) -> Sequence[answer.NotDone]:
    match read:
        case ticketreader.Items():
            return []
        case ticketreader.NotInForm():
            return _not_done(answer.Why.TICKET_FORM, read.problem)
        case _:  # pragma: no cover
            assert_never(read)


def _pushed_to(check: actfacts.Pushing) -> Sequence[answer.NotDone]:
    # the branch and the commit a push is given: no default branch, no empty commit
    if check.assigned in DEFAULT_BRANCHES:
        line = f"{check.assigned} is a default branch: a push goes to a PR's branch"
        return _not_done(answer.Why.DEFAULT_BRANCH, line)
    if check.empty:
        line = "an empty commit: a revision of the body alone is `pitboss act pr-edit`"
        return _not_done(answer.Why.EMPTY_COMMIT, line)
    return []


def _branch(check: actfacts.Pushing) -> Sequence[answer.NotDone]:
    if check.current == check.assigned:
        return []
    on = check.current or "a detached head"
    line = f"the worktree is on {on}, and dispatch assigned {check.assigned}"
    return _not_done(answer.Why.OTHER_BRANCH, line)


def _prepush(check: actfacts.Pushing) -> Sequence[answer.NotDone]:
    last = (check.output.strip().splitlines() or [""])[-1]
    if check.status == 0 and last == "ok":
        return []
    line = f"the pre-push check did not say ok (exit {check.status}):"
    return _not_done(answer.Why.PRE_PUSH, f"{line} {check.output.strip()[-60:]}")


def _worktree(check: actfacts.Worktree) -> Sequence[answer.NotDone]:
    if check.changes:
        line = "KEPT: the worktree has changes not committed"
        return _not_done(answer.Why.KEPT_CHANGES, line)
    if check.unpushed:
        line = f"KEPT: a commit on no remote branch: {check.unpushed}"
        return _not_done(answer.Why.KEPT_UNPUSHED, line)
    return []


def check_row(read: actfacts.ActRead, held: holdparse.Held) -> Sequence[answer.NotDone]:
    """What the facts the verb's own decision turns on say stands.

    Args:
        read: what the verb is decided from.
        held: each repository's holds.

    Returns:
        What stands, in the order the facts were read.
    """
    return [each for check in read.checks for each in _check(check)]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Rows:
    """The rows of an act verb's decision, in order.

    Attributes:
        owner: the owner's messages with no disposition.
        hold: the holds that cover the verb.
        checks: the facts the verb's own decision turns on.
    """

    owner: RowRule
    hold: RowRule
    checks: RowRule


ROWS = Rows(owner=owner_row, hold=hold_row, checks=check_row)


def verdict(read: actfacts.ActRead, held: holdparse.Held, rows: Rows) -> answer.Acting:
    """The decision on the act verb the command asks for.

    Args:
        read: what it is decided from.
        held: each repository's holds.
        rows: the rows (``ROWS``).

    Returns:
        ``NotDone`` with the first that stands, else None; None for a command
        that asks for no verb.
    """
    gated = [rows.owner, rows.hold] if read.verb not in UNGATED else []
    found = [each for row in [*gated, rows.checks] for each in row(read, held)]
    return found[0] if read.verb and found else None
