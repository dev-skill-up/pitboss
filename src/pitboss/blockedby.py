"""A PR that waits for another PR or a ticket (keyword: blocked-by, quire#1116).

quire#1116 could not go green until quire#1110 merged, and the sweep kept offering
its CI fix. A PR declares what it waits for with ``Blocked-by: owner/name#N``
(``blockedform``), one line for each blocker. Each blocker is read once, and the PR's
step becomes:

* a blocker that is open: WAIT_FOR_BLOCKER naming it; no fix, review or merge;
* a loop (A blocked by B blocked by A, found within ``LIMIT`` reads): FIX_BLOCKED_BY
  and a ``BLOCKER LOOP`` line, never a wait for each other;
* a blocker closed without merging, or unreadable: FIX_BLOCKED_BY and a
  ``BLOCKER GONE`` line;
* every blocker merged after the PR's red checks finished: AFTER_BLOCKER (merge the
  base into the branch, check, push, so CI runs again); once the head is newer the
  PR is at its own step.

Shapes derived from the code and the register: a PR needing another PR merged, a
relock pin waiting for a package publish (the PR names the publishing PR or
ticket), and merge-queue ordering (the later PR names the earlier) are this form; a
ticket blocked by a ticket (``ticketblock``) and a hold (``WAIT_FOR_HOLD``) were
modelled before; a folded ticket is one PR for several tickets (``folds``). A
tracking ticket's ``closes when`` is ``ticketblock``'s.
"""

import dataclasses
import enum
from typing import Mapping, MutableMapping, Sequence

from . import config, ghapi, pulls, shapes, steps, ticketblock, ticketdata

LIMIT = 32  # the most blockers read to look for a loop
KEPT = steps.WAITS | {steps.Step.WAIT_FOR_OWNER, steps.Step.WAIT_FOR_HOLD}


class State(enum.Enum):
    """What a blocker is.

    Attributes:
        OPEN: still open.
        MERGED: merged.
        CLOSED: closed without merging.
        UNREADABLE: the API does not give it.
    """

    OPEN = enum.auto()
    MERGED = enum.auto()
    CLOSED = enum.auto()
    UNREADABLE = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Blocker:
    """A ticket or PR another PR waits for.

    Attributes:
        reference: ``owner/name#number``.
        state: what it is.
        merged_at: when it merged (ISO 8601), else empty.
        body: its text.
    """

    reference: str
    state: State
    merged_at: str = ""
    body: str = ""


CLOSED = frozenset({State.CLOSED, State.UNREADABLE})


def read(github: ghapi.GitHub, reference: str) -> Blocker:
    """Read a blocker.

    Args:
        github: the API.
        reference: ``owner/name#number``.

    Returns:
        The blocker; ``UNREADABLE`` when the API cannot give it.
    """
    found = ticketdata.read(github, reference)
    if found is None:
        return Blocker(reference=reference, state=State.UNREADABLE)
    state = State.OPEN if found.open else State.CLOSED
    return Blocker(
        reference=reference,
        state=State.MERGED if found.merged_at else state,
        merged_at=found.merged_at,
        body=found.body,
    )


def declared(pull: pulls.PullFacts) -> Sequence[str]:
    """What the body of a PR says it waits for.

    Args:
        pull: the PR.

    Returns:
        The references, each once, never the PR itself.
    """
    names = ticketblock.named(pull.pull.body, pull.repo)
    return [each for each in dict.fromkeys(names) if each != pulls.reference(pull)]


def loop(
    seen: MutableMapping[str, Blocker], github: ghapi.GitHub, start: str, first: str
) -> Sequence[str]:
    """The chain of blockers that leads from a PR back to itself.

    Args:
        seen: the blockers read so far (it grows).
        github: the API.
        start: the PR, ``owner/name#number``.
        first: the blocker to follow.

    Returns:
        The references from ``start`` to ``start``, or none when the chain ends
        or ``LIMIT`` blockers were followed.
    """
    todo = [[start, first]]
    visited: set[str] = set()
    while todo and len(visited) < LIMIT:
        path = todo.pop()
        if path[-1] == start:
            return path
        if path[-1] not in visited:
            visited.add(path[-1])
            found = seen.setdefault(path[-1], read(github, path[-1]))
            more = ticketblock.named(found.body, config.repo_of(path[-1]))
            todo += [[*path, each] for each in more if found.state is State.OPEN]
    return []


def _red_since(pull: pulls.PullFacts, merged: str) -> bool:
    # the head is red, and every failed check ended before the blockers merged
    failing = pulls.failed_checks(pull)
    last = max(map(_ended, failing), default="")
    return bool(last) and last < merged and steps.Task.FIX_CI is pull.step.task


def _ended(check: shapes.CheckRun) -> str:
    return check.completed_at


def verdict(
    pull: pulls.PullFacts, found: Sequence[Blocker], path: Sequence[str]
) -> tuple[steps.Next | None, str]:
    """The step a PR has because of what it waits for, and the sweep's line.

    Args:
        pull: the PR.
        found: its blockers as read.
        path: the loop through it, or none.

    Returns:
        The step (None when the PR keeps its own) and the line (empty then).
    """
    me = pulls.reference(pull)
    shut = [each.reference for each in found if each.state in CLOSED]
    live = [each.reference for each in found if each.state is State.OPEN]
    when = max((each.merged_at for each in found), default="")
    fix = steps.worker(steps.Task.FIX_BLOCKED_BY)
    if path:
        return fix, f"BLOCKER LOOP {' -> '.join(path)}: each waits for the next"
    if shut:
        return fix, f"BLOCKER GONE {me}: {shut[0]} is closed unmerged"
    if live:
        wait = steps.Next(step=steps.Step.WAIT_FOR_BLOCKER, comment=", ".join(live))
        return wait, f"BLOCKER WAIT {me}: waits for {wait.comment}"
    if _red_since(pull, when):
        after = steps.worker(steps.Task.AFTER_BLOCKER)
        return after, f"BLOCKER MERGED {me}: merged at {when}, after its red check"
    return None, ""


def _settled(
    github: ghapi.GitHub, seen: MutableMapping[str, Blocker], pull: pulls.PullFacts
) -> tuple[pulls.PullFacts, str]:
    names = declared(pull)
    if not names or pull.step.step in KEPT:
        return pull, ""
    for each in names:
        seen.setdefault(each, read(github, each))
    me = pulls.reference(pull)
    chains = [loop(seen, github, me, each) for each in names]
    step, line = verdict(
        pull, [seen[each] for each in names], next(filter(None, chains), [])
    )
    return (dataclasses.replace(pull, step=step) if step else pull), line


def settle(
    github: ghapi.GitHub, reads: Sequence[pulls.Read]
) -> tuple[Sequence[pulls.Read], Mapping[str, str]]:
    """Give each PR that declares a blocker the step the blocker calls for.

    Args:
        github: the API.
        reads: every open PR.

    Returns:
        The PRs, and the sweep's line for each that was changed, by reference.
    """
    seen: MutableMapping[str, Blocker] = {}
    settled: list[pulls.Read] = []
    said: dict[str, str] = {}
    for each in reads:
        if isinstance(each, shapes.Unreadable):
            settled.append(each)
            continue
        changed, line = _settled(github, seen, each)
        settled.append(changed)
        if line:
            said[pulls.reference(each)] = line
    return settled, said
