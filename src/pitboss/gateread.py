"""What a PR at the merge or the undraft step is gated on, read once (keyword: gate).

``readworld`` calls it for each such PR it examines, so the decision carries the
rows ``act`` ran before it merged (``gate``). The PR object, the head's runs and
its statuses are the fields of the PR's own read (``pulls``), not read again; the
inputs no field holds are read here once (``gateinputs``): the repository's rules,
the files, the tickets the body closes, the blockers, the timeline and the
Max-lines of the repository; its holds are the world's (``holdissues``). A status
GitHub answers (a 404) is kept as the answer.
"""

import functools
import json
from typing import Callable, Sequence

from . import concurrently, gatefacts, gateinputs, ghapi, pullobject, pullrecords
from . import pulls, pullstate, reviews, shapes, world
from .totaljson import name_at, records

MERGED_WANTED = 100


def _closed_page(repo: str, number: int) -> str:
    # the repository's closed PRs, newest created first
    query = "state=closed&sort=created&direction=desc"
    return f"repos/{repo}/pulls?{query}&per_page={ghapi.PAGE_SIZE}&page={number}"


def _merged(github: ghapi.GitHub, repo: str, page: int, wanted: int) -> list[int]:
    # the numbers of the newest created merged PRs, page by page until enough
    rows = records(ghapi.get_json(github, _closed_page(repo, page)))
    found = [int(str(row["number"])) for row in rows if row.get("merged_at")]
    if len(rows) < ghapi.PAGE_SIZE or len(found) >= wanted:
        return found[:wanted]
    return found + _merged(github, repo, page + 1, wanted - len(found))


def _p90(github: ghapi.GitHub, repo: str) -> int:
    # the size of 90 of the 100 newest merged PRs; none merged is 0, so every
    # size needs a ruling
    numbers = _merged(github, repo, 1, MERGED_WANTED)
    pulls_read = concurrently.each(
        lambda number: ghapi.get_object(github, f"repos/{repo}/pulls/{number}"),
        numbers,
    )
    sizes = sorted(
        sum(int(str(each.get(key, 0))) for key in ("additions", "deletions"))
        for each in pulls_read
    )
    return sizes[(9 * len(sizes) + 9) // 10 - 1] if sizes else 0


def limits(github: ghapi.GitHub) -> Callable[[str], int]:
    """Each repository's 90th percentile of the lines its last 100 merged PRs changed.

    Args:
        github: the reading runner.

    Returns:
        What reads a repository's percentile (0 when it has no merged PR) once,
        when first asked.
    """
    return functools.cache(lambda repo: _p90(github, repo))


def _events(sources: reviews.Sources) -> Sequence[pullrecords.Event]:
    # the PR's comments and reviews as the gate's events, oldest first: the
    # PR's own read of them, not its timeline read again
    said = [
        (each.created_at, _as_event("commented", "", each)) for each in sources.comments
    ]
    said += [
        (each.submitted_at, _as_event("reviewed", each.state, each))
        for each in sources.reviews
    ]
    return [event for _, event in sorted(said, key=lambda each: each[0])]


def _as_event(
    kind: str, state: str, each: shapes.Comment | shapes.PullReview
) -> pullrecords.Event:
    return pullrecords.Event(
        kind=kind, state=state, login=each.login, body=each.body, label=""
    )


def _head(pull: pulls.PullRead) -> pullstate.Head:
    # the head's runs and statuses and the PR's events, as its own read typed them
    statuses = [
        pullrecords.Status(context=each.context, state=each.state)
        for each in pull.posted.statuses
    ]
    return pull.checks, statuses, _events(pull.posted.sources)


def _inputs(
    read: gateinputs.Read, given: gateinputs.Settings, pull: pulls.PullRead
) -> pullobject.Raw:
    # the inputs no field of the PR's own read holds
    repo, number = pull.repo.slug, pull.pull.number
    named = (pull.pull.body, pull.pull.base)
    return {
        **gateinputs.repo_reads(read, repo, number, named),
        **gateinputs.said(given, repo),
    }


def reader(github: ghapi.GitHub) -> world.GateRead:
    """What reads a PR's gate.

    Args:
        github: the API (its reads are tried again, then fail).

    Returns:
        The reader; the login and each repository's Max-lines are read once,
        when first needed.
    """
    read = gateinputs.reader(github)
    identity = functools.cache(lambda: identity_of(github))
    limit = limits(github)

    def gated(
        pull: pulls.PullRead, holds: Sequence[pullrecords.Hold]
    ) -> gatefacts.Gate:
        given = gateinputs.Settings(
            identity=identity(), authors=[identity()], max_lines=limit
        )
        inputs = _inputs(read, given, pull)
        return pullstate.gate_read(pull.posted.object, inputs, _head(pull), holds)

    return gated


def identity_of(github: ghapi.GitHub) -> str:
    """The login ``gh`` is signed in as.

    Args:
        github: the reading runner.

    Returns:
        The login.
    """
    return name_at(json.loads(github.run(["gh", "api", "user"]).stdout), "login")
