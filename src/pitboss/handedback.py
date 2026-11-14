"""A slot is done once its worker's hand-back is recorded (keyword: hand-back-done).

The worker of pitboss#467 handed back more than ten times and stayed listed as
running, so its slot looked full (pitboss#471). ``hand-back-check`` records the
head it accepted in the worktree's git directory; a slot whose PR's head is a
recorded head of the PR's worktree is counted done, whatever the harness lists.
"""

import argparse
import pathlib
import subprocess
from typing import AbstractSet, Iterable, Mapping, Sequence

from . import ghapi, handbackrecord, ledger, listed, local, nextfound, running
from . import slotholder
from .totaljson import text


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


def _recorded(found: nextfound.Found, row: listed.Listed) -> bool:
    # the row of a slot's PR has no branch or head (keyword: org-search): the PR
    # is read for them, one read for each slot held
    head = _head(found, row)
    directory = _worktree_dir(found, text(head.get("ref")))
    return directory is not None and handbackrecord.recorded(
        directory, text(head.get("sha"))
    )


def head_of(found: nextfound.Found, row: listed.Listed) -> str:
    """The head commit of an open PR, read (its search row has none, org-search).

    Args:
        found: the context.
        row: the PR's row.

    Returns:
        The commit; empty when GitHub gives none.
    """
    return text(_head(found, row).get("sha"))


def _head(found: nextfound.Found, row: listed.Listed) -> Mapping[str, object]:
    pull = ghapi.get_object(found.github, f"repos/{row.repo.slug}/pulls/{row.number}")
    head = pull.get("head")
    return head if isinstance(head, dict) else {}


def _done(
    found: nextfound.Found, slot: ledger.Slot, rows: Sequence[listed.Listed]
) -> bool:
    wanted = {slot.task, slot.ticket}
    return any(
        wanted & {*row.works_on, row.reference} and _recorded(found, row)
        for row in rows
    )


def slots(
    found: nextfound.Found, rows: Sequence[listed.Listed], book: ledger.Ledger
) -> Sequence[ledger.Slot]:
    """The slots whose worker's PR head is a recorded hand-back.

    Args:
        found: the context.
        rows: the open PRs, as listed.
        book: the ledger.

    Returns:
        The slots with an agent whose PR (the slot's task or ticket) holds a
        head that ``hand-back-check`` accepted in the PR's worktree.
    """
    held = [each for each in book.slots if each.agent and (each.task or each.ticket)]
    return [each for each in held if _done(found, each, rows)]


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


def ledger_after_hand_backs(
    found: nextfound.Found, rows: Sequence[listed.Listed], book: ledger.Ledger
) -> ledger.Ledger:
    """The ledger less the slots whose worker handed back (keyword: hand-back-done).

    Args:
        found: the context.
        rows: the open PRs, as listed.
        book: the ledger as the live agents make it.

    Returns:
        The ledger, each slot whose worker's PR head is a recorded hand-back empty.
    """
    done = release(found.args, (each.agent for each in slots(found, rows, book)))
    return slotholder.without(book, done)
