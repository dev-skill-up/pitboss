"""The task list every dispatch and hand-back prints, and ``slots tasklist``.

(Keyword: tasklist-state, pitboss#471.) The list is made of the ledger and
GitHub (``tasklist.checklist``), in the format ``update_progress_checklist``
takes, so the orchestrator's checklist is replaced by this output and never kept
by hand.
"""

from typing import Sequence

from . import ledger, mergedlist, nextfound, tasklist, work


def print_list(
    found: nextfound.Found, live: ledger.Ledger, items: Sequence[work.Item]
) -> None:
    """Print the task list of the real state.

    Args:
        found: the context.
        live: the ledger of the agents that run.
        items: the queued items.
    """
    merged = mergedlist.lately(found.github, found.settings, found.now)
    for each in tasklist.checklist(live, items, merged):
        print(each)
