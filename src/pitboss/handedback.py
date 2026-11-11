"""A slot is done once its worker's hand-back is recorded (keyword: hand-back-done).

The worker of pitboss#467 handed back more than ten times and stayed listed as
running, so its slot looked full (pitboss#471). ``hand-back-check`` records the
head it accepted in the worktree's git directory; a slot whose PR's head is a
recorded head of the PR's worktree is counted done, whatever the harness lists.
"""

import argparse
import pathlib
import subprocess
from typing import AbstractSet, Iterable, Sequence

from . import (
    handbackrecord,
    ledger,
    local,
    nextfound,
    pulls,
    running,
    work,
)


def _worktree_dir(found: nextfound.Found, branch: str) -> pathlib.Path | None:
    run = found.args.safe_run
    clone = found.settings.project.main_clone
    try:
        listed = local.parse_worktrees(
            running.git(run, clone, "worktree", "list", "--porcelain")
        )
        path = next(each.path for each in listed if each.branch == branch)
        return pathlib.Path(
            running.git(run, path, "rev-parse", "--absolute-git-dir").strip()
        )
    except (subprocess.CalledProcessError, OSError, StopIteration):
        return None


def _recorded(found: nextfound.Found, pull: pulls.PullFacts) -> bool:
    directory = _worktree_dir(found, pull.pull.head.branch)
    return directory is not None and handbackrecord.recorded(
        directory, pull.pull.head.sha
    )


def _done(
    found: nextfound.Found, slot: ledger.Slot, facts: Sequence[pulls.PullFacts]
) -> bool:
    wanted = {slot.task, slot.ticket}
    return any(
        wanted & (work.taken([pull]) | {pulls.reference(pull)})
        and _recorded(found, pull)
        for pull in facts
    )


def slots(
    found: nextfound.Found, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> Sequence[ledger.Slot]:
    """The slots whose worker's PR head is a recorded hand-back.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the ledger.

    Returns:
        The slots with an agent whose PR (the slot's task or ticket) holds a
        head that ``hand-back-check`` accepted in the PR's worktree.
    """
    held = [each for each in book.slots if each.agent and (each.task or each.ticket)]
    facts = pulls.readable(opened) if held else []
    return [each for each in held if _done(found, each, facts)]


def release(args: argparse.Namespace, agents: Iterable[str]) -> AbstractSet[str]:
    """Drop the workers that handed back from the agents the session runs.

    The harness lists such a worker as running; counted so, it would be an
    unrecorded agent holding no slot (pitboss#471).

    Args:
        args: the parsed arguments; ``running`` is cut of the agents.
        agents: the agents whose slot is done.

    Returns:
        The agents.
    """
    done = frozenset(agents)
    running = getattr(args, "running", None)
    if running is not None:
        args.running = [each for each in running if each not in done]
    return done


def agents(
    found: nextfound.Found, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> AbstractSet[str]:
    """The workers of ``slots`` that handed back, cut from the running agents.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the ledger.

    Returns:
        Their agents.
    """
    return release(found.args, (each.agent for each in slots(found, opened, book)))
