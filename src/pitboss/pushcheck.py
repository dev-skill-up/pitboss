"""What a push did, read back from the remote (keyword: push-readback, pitboss#457).

``git push`` exits 0 for a push that moved nothing, so ``pitboss push`` reads each
pushed ref before and after with ``git ls-remote`` and compares it with the local
commit. The result of a push is one :class:`Outcome` with a :class:`Kind` per case,
and each outcome has one line, :func:`line`.
"""

import dataclasses
import enum
import itertools
import subprocess
from typing import Sequence

from .running import Run

_HEADS = "refs/heads/"
UNREADABLE = "(unreadable)"


class Kind(enum.Enum):
    """The four things a push can come to.

    Attributes:
        MOVED: the remote moved to the local head.
        ALREADY: the remote already held the local head.
        REFUSED: git refused the push.
        UNMOVED: the push ran and the remote did not move.
    """

    MOVED = "the remote moved to the local head"
    ALREADY = "the remote already held the local head"
    REFUSED = "git refused the push"
    UNMOVED = "the push ran and the remote did not move"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Target:
    """One ref a push is to move.

    Attributes:
        remote: the remote's name or URL.
        url: where a push to the remote goes (its push URL).
        ref: the full name of the ref on the remote.
        local: the commit the push is to put there.
        before: what the remote held before the push (empty: nothing).
    """

    remote: str
    url: str
    ref: str
    local: str
    before: str


NOTHING = Target(remote="", url="", ref="", local="", before="")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """The result of a push, or of one ref of it.

    Attributes:
        kind: which case.
        target: the ref; ``NOTHING`` for a refused push, which names none.
        after: what the remote holds after the push (empty: nothing).
        code: git's exit status of a refused push.
        message: git's own message of a refused push.
    """

    kind: Kind
    target: Target
    after: str = ""
    code: int = 0
    message: str = ""


def _out(run: Run, command: Sequence[str]) -> str | None:
    # the output of a read, None when git fails
    try:
        return run(command).stdout.strip()
    except subprocess.CalledProcessError:
        return None


def read_remote(run: Run, remote: str, ref: str) -> str:
    """The commit a remote holds at a ref.

    Args:
        run: the runner of read-only commands.
        remote: the remote.
        ref: the full ref name.

    Returns:
        The commit; empty when the ref is absent, ``UNREADABLE`` when git fails.
    """
    shown = _out(run, ["git", "ls-remote", remote, ref])
    if shown is None:
        return UNREADABLE
    found = [each.split("\t") for each in shown.splitlines()]
    return next((commit for commit, name in found if name == ref), "")


def _destination(destination: str, current: str) -> str:
    named = current if destination == "HEAD" else destination
    if not named:
        return ""
    return named if named.startswith("refs/") else _HEADS + named


def _push_url(run: Run, remote: str) -> str:
    # a remote's pushurl may differ from its url; a URL given as the remote is itself
    return _out(run, ["git", "remote", "get-url", "--push", remote]) or remote


def _refspecs(refspecs: Sequence[str], current: str) -> Sequence[tuple[str, str]]:
    # (source, full destination ref) of each refspec that is not a deletion
    split = [each.lstrip("+").partition(":") for each in refspecs]
    return [(a, _destination(c or a, current)) for a, _, c in split if a]


def targets(run: Run, arguments: Sequence[str], current: str) -> Sequence[Target]:
    """The refs a ``git push`` with these arguments moves, as far as they can be told.

    Args:
        run: the runner of read-only commands.
        arguments: the arguments after ``push``; no refspec means ``HEAD``. A
            refspec that deletes, or whose source is no commit, is left out.
        current: the current branch, empty for a detached head.

    Returns:
        A target for each refspec, with what the remote holds now.
    """
    named = list(itertools.filterfalse(lambda each: each[:1] == "-", arguments))
    remote = named[0] if named else "origin"
    url = _push_url(run, remote)
    refs = _refspecs(named[1:] or ["HEAD"], current)
    verify = ["git", "rev-parse", "--verify", "-q"]
    commits = [(_out(run, [*verify, a]), r) for a, r in refs]
    return [
        Target(remote=remote, url=url, ref=r, local=c, before=read_remote(run, url, r))
        for c, r in commits
        if c and r
    ]


def judge(run: Run, target: Target) -> Outcome:
    """Read the remote after a push that exited 0 and say what it came to.

    Args:
        run: the runner of read-only commands.
        target: the ref, as it was before the push.

    Returns:
        ``ALREADY`` when the remote held the local commit before, ``MOVED`` when
        it holds it now, else ``UNMOVED``.
    """
    after = read_remote(run, target.url, target.ref)
    if after != target.local:
        return Outcome(kind=Kind.UNMOVED, target=target, after=after)
    kind = Kind.ALREADY if target.before == target.local else Kind.MOVED
    return Outcome(kind=kind, target=target, after=after)


def line(outcome: Outcome) -> str:
    """The one line an outcome prints.

    Args:
        outcome: the outcome.

    Returns:
        The line; a refused push's line is followed by git's message.
    """
    target = outcome.target
    if outcome.kind is Kind.REFUSED:
        return (
            f"git push failed (exit {outcome.code}): nothing was recorded\n"
            f"{outcome.message}"
        )
    where = f"{target.remote} {target.ref}"
    if outcome.kind is Kind.MOVED:
        return "pushed"
    if outcome.kind is Kind.ALREADY:
        return f"already pushed: {where} already held {target.local}"
    return (
        f"push FAILED: git push exited 0 but {where} holds"
        f" {outcome.after or 'nothing'} and the local head is {target.local}"
    )
