"""A PR that waits for another PR or a ticket (keyword: blocked-by, quire#1116).

quire#1116 could not go green until quire#1110 merged, and the sweep kept offering
its CI fix. A PR declares what it waits for with ``Blocked-by: owner/name#N``
(``blockedform``), one line for each blocker. Each blocker is read once, and the PR's
step becomes:

* a blocker that is open: no step (``steps.Idle``), so no line names the PR; the
  blocker has its own decision in its place (keyword: one-path);
* a loop (A blocked by B blocked by A, found within ``LIMIT`` reads): FIX_BLOCKED_BY,
  never a wait for each other;
* a blocker closed without merging, or unreadable: FIX_BLOCKED_BY;
* every blocker merged after the PR's red checks finished: AFTER_BLOCKER (merge the
  base into the branch, check, push, so CI runs again); once the head is newer the
  PR is at its own step.

Shapes derived from the code and the register: a PR needing another PR merged, a
relock pin waiting for a package publish (the PR names the publishing PR or
ticket), and merge-queue ordering (the later PR names the earlier) are this form; a
ticket blocked by a ticket (``ticketblock``) and a hold of the runners were
modelled before; a folded ticket is one PR for several tickets (``folds``). A
tracking ticket's ``closes when`` is ``ticketblock``'s.
"""

import dataclasses
from typing import MutableMapping, Sequence

from . import blockedstep, configrepos, ghapi, pullfacts, pullref, ticketblock
from . import ticketdata
from .blockedstep import Blocker, Closure, State

LIMIT = 32  # the most blockers read to look for a loop


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
        return Blocker(
            reference=reference, state=State.UNREADABLE, merged_at="", body=""
        )
    state = State.OPEN if found.open else State.CLOSED
    return Blocker(
        reference=reference,
        state=State.MERGED if found.merged_at else state,
        merged_at=found.merged_at,
        body=found.body,
    )


def declared(pull: pullfacts.PullFacts) -> Sequence[str]:
    """What the body of a PR says it waits for.

    Args:
        pull: the PR.

    Returns:
        The references, each once, never the PR itself.
    """
    names = ticketblock.named(pull.pull.body, pull.repo)
    return [each for each in dict.fromkeys(names) if each != pullref.reference(pull)]


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
            more = ticketblock.named(found.body, configrepos.repo_of(path[-1]))
            todo += [[*path, each] for each in more if found.state is State.OPEN]
    return []


def read_closure(github: ghapi.GitHub, pull: pullfacts.PullFacts) -> Closure:
    """Read what a PR's ``Blocked-by:`` lines name: its closure (plan 3.1, point 4).

    Args:
        github: the API.
        pull: the PR.

    Returns:
        Each blocker as read, and whether a chain of them leads back to the PR.
    """
    names = declared(pull)
    seen: MutableMapping[str, Blocker] = {}
    for each in names:
        seen.setdefault(each, read(github, each))
    me = pullref.reference(pull)
    looped = any(loop(seen, github, me, each) for each in names)
    return Closure(found=[seen[each] for each in names], looped=looped)


def at_blockers(github: ghapi.GitHub, pull: pullfacts.PullFacts) -> pullfacts.PullFacts:
    """A PR at the step its blockers give it: a shared red's other holder.

    Args:
        github: the API.
        pull: the PR.

    Returns:
        The PR, its step settled by its blockers as read.
    """
    moved = blockedstep.step_of(pull, read_closure(github, pull))
    return dataclasses.replace(pull, step=moved or pull.step)
