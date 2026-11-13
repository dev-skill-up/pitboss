"""What a PR at the merge or the undraft step is gated on, read once (keyword: gate).

``readworld`` calls it for each such PR it examines, so the decision carries the
rows ``act`` ran before it merged (``gate``). The PR object, the head's runs and
its statuses are the fields of the PR's own read (``pulls``), not read again; the
inputs no field holds are read here once (``gateinputs``): the repository's rules,
the files, the tickets the body closes, the blockers, the timeline, the holds and
the Max-lines of the repository. A status GitHub answers (a 404) is kept as the
answer.
"""

import functools
import json
from typing import Callable, Sequence

from . import gatefacts, gateinputs, ghapi, pullobject, pullrecords, pulls
from . import pullstate, reviews, shapes, workorder, world
from .textparts import split_at
from .totaljson import at, name_at, records

HOLD_LABEL = "pitboss-hold"
SIZES = (
    "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name)"
    " { pullRequests(last: 100, states: MERGED) { nodes { additions deletions } } } }"
)


def _p90(github: ghapi.GitHub, repo: str) -> int:
    # the size of 90 of 100 merged PRs; none merged is 0, so every size needs a
    # ruling
    owner, name = split_at(repo, "/")
    words = ["gh", "api", "graphql", "-f", f"query={SIZES}"]
    words += ["-f", f"owner={owner}", "-f", f"name={name}"]
    nodes = records(
        at(ghapi.run_json(github, words), "data", "repository", "pullRequests", "nodes")
    )
    sizes = sorted(
        sum(int(str(each.get(key, 0))) for key in ("additions", "deletions"))
        for each in nodes
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


def holds_of(read: gateinputs.Read, repo: str) -> object:
    """The holds of a repository: its open issues labelled ``pitboss-hold``.

    Args:
        read: reads one path.
        repo: ``owner/name``.

    Returns:
        The issues as GitHub answered; ``pullstate`` reads their scope.
    """
    return read(gateinputs.ALL + workorder.labelled_path(repo, HOLD_LABEL))


def _of_run(check: shapes.CheckRun) -> pullrecords.Run:
    status, conclusion = check.said
    return pullrecords.Run(
        name=check.name,
        status=status,
        conclusion=conclusion,
        number=check.id,
        started_at=check.started_at,
    )


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
    runs = [_of_run(each) for each in pull.checks]
    return runs, statuses, _events(pull.posted.sources)


def _inputs(
    read: gateinputs.Read, given: gateinputs.Settings, pull: pulls.PullRead
) -> pullobject.Raw:
    # the inputs no field of the PR's own read holds
    repo, number = pull.repo.slug, pull.pull.number
    named = (pull.pull.body, pull.pull.base)
    return {
        **gateinputs.repo_reads(read, repo, number, named),
        **gateinputs.said(given, repo),
        "holds": holds_of(read, repo),
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

    def gated(pull: pulls.PullRead) -> gatefacts.Gate:
        given = gateinputs.Settings(
            identity=identity(), authors=[identity()], max_lines=limit
        )
        inputs = _inputs(read, given, pull)
        return pullstate.gate_read(pull.posted.object, inputs, _head(pull))

    return gated


def identity_of(github: ghapi.GitHub) -> str:
    """The login ``gh`` is signed in as.

    Args:
        github: the reading runner.

    Returns:
        The login.
    """
    return name_at(json.loads(github.run(["gh", "api", "user"]).stdout), "login")
