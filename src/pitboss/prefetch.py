"""Reads of ``slots next`` started while the open PRs are read (keyword: prefetch).

The full ``slots next`` waited for each stage before it asked for the next, yet
the first page of the top priority's tickets, the causes since last time and the
search for unlabeled tickets do not depend on the open PRs. They are started at
once, on the runner that remembers its reads (``ghmemo``), so that the stage that
asks for them takes the answers (pitboss#453). A read that fails here fails
again where it is taken, with the same error.
"""

import concurrent.futures
from typing import Callable, Sequence

from . import config, configrepos, ghapi, ticketwindow, unlabeledsearch, windowstage
from .nextfound import Found


def quietly(read: Callable[[], object]) -> bool:
    """Make a read, and leave its failure for the stage that takes the answer.

    Args:
        read: the read.

    Returns:
        True when the read was made, False when it failed.
    """
    try:
        read()
    except Exception:  # the stage that takes the answer raises it
        return False
    return True


def start(found: Found) -> concurrent.futures.Executor:
    """Start the reads that do not wait for the open PRs.

    Args:
        found: the context.

    Returns:
        The executor they run in; its threads end with the process.
    """
    settings = found.settings
    github: ghapi.GitHub = found.github
    repos: Sequence[config.Repo] = configrepos.repositories(settings)
    top = settings.slots.priority_labels[:1]
    steps: list[Callable[[], object]] = [
        lambda: windowstage.warm(found),
        lambda: unlabeledsearch.references(github, settings),
        *(
            (lambda name=name: ticketwindow.first_pages(github, repos, name))
            for name in top
        ),
    ]
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(steps))
    for task in steps:
        pool.submit(quietly, task)
    pool.shutdown(wait=False)
    return pool
