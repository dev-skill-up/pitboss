"""What an act verb's decision is made from, as read (plan 6.1; keyword: act-verbs).

``actread`` reads these once, in the command's one read, and ``actdecide`` decides
from them; nothing here reads or decides. Each fact is what the platform said: the
owner's messages with no disposition, and for the verbs that need one, the fact
their decision turns on (a size and the repository's p90, the PRs that close a
ticket, a comment's author, a ticket body's form, the worktree's branch and state,
the pre-push check's answer).
"""

import dataclasses
from typing import Sequence

from . import actport, ticketreader

Asked = actport.Asked  # the verb a command line asks for (``actport``)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Size:
    """``act ticket``: the size asked and the repository's 90th percentile.

    Attributes:
        repo: the repository.
        lines: the ticket's Max-lines.
        p90: the repository's 90th percentile of changed lines.
        ruled: whether a ruling names the size.
    """

    repo: str
    lines: int
    p90: int
    ruled: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Starters:
    """``act ticket-edit``: the open PRs that close the ticket.

    Attributes:
        ticket: the ticket, ``owner/name#number``.
        pulls: their numbers.
    """

    ticket: str
    pulls: Sequence[int]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Authored:
    """``act comment-edit`` and ``comment-delete``: who posted the comment.

    Attributes:
        ours: whether ``pitboss act`` posted it.
        keyed: its first line that starts with a review or act key, empty for
            none (such a comment is a review or a record, never evidence).
    """

    ours: bool
    keyed: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class TicketForm:
    """``act ticket-edit`` and ``pr-create``: the ticket body as the reader reads it.

    Attributes:
        read: its items, or what is not in the form.
    """

    read: ticketreader.Read


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pushing:
    """``act push``: the worktree's branch, its head and the pre-push check's answer.

    Attributes:
        current: the branch the worktree is on, empty for a detached head.
        assigned: the branch dispatch assigned.
        empty: the head commit's tree is its parent's (it changes nothing).
        status: the pre-push check's exit status.
        output: what it printed.
    """

    current: str
    assigned: str
    empty: bool
    status: int
    output: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Worktree:
    """``act clean``: what a finished worktree holds that no remote has.

    Attributes:
        changes: whether it has changes not committed.
        unpushed: its first commit on no remote branch, empty for none.
    """

    changes: bool
    unpushed: str


Check = Size | Starters | Authored | TicketForm | Pushing | Worktree


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ActRead:
    """What one act verb's decision is made from.

    Attributes:
        verb: the verb, empty when the command is no act verb.
        repos: the repositories it covers (its target's, or every one for all).
        pending: the owner's messages that have no disposition, in order.
        checks: the facts its own decision turns on, in the order they are read.
    """

    verb: str
    repos: Sequence[str]
    pending: Sequence[str]
    checks: Sequence[Check]


NO_ACT = ActRead(verb="", repos=(), pending=(), checks=())  # no verb was asked
