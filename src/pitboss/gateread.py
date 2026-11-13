"""What a PR at the merge or the undraft step is gated on, read once (keyword: gate).

``readworld`` calls it for each such PR it examines, so the decision carries the
rows ``act`` ran before it merged (``gate``). The inputs are those the act verdict
read (``actinputs``): the PR object, the repository's rules, the head's runs and
statuses, the files, the tickets the body closes, the blockers, the timeline,
the holds and the Max-lines of the repository. A read that fails after its tries
fails the command (``retrying``); a status GitHub answers (a 404) is kept as the
answer.
"""

import functools
import json
from typing import Callable

from . import (
    actinputs,
    gatefacts,
    ghapi,
    pulls,
    pullstate,
    workorder,
    world,
)
from .textparts import split_at
from .totaljson import at, members, name_at, records

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


def holds_of(read: actinputs.Read, repo: str) -> object:
    """The holds of a repository: its open issues labelled ``pitboss-hold``.

    Args:
        read: reads one path.
        repo: ``owner/name``.

    Returns:
        The issues as GitHub answered; ``pullstate`` reads their scope.
    """
    return read(actinputs.ALL + workorder.labelled_path(repo, HOLD_LABEL))


def reader(github: ghapi.GitHub) -> world.GateRead:
    """What reads a PR's gate.

    Args:
        github: the API (its reads are tried again, then fail).

    Returns:
        The reader; the login and each repository's Max-lines are read once,
        when first needed.
    """
    read = actinputs.reader(github)
    identity = functools.cache(lambda: identity_of(github))
    limit = limits(github)

    def gated(pull: pulls.PullFacts) -> gatefacts.Gate:
        repo, number = pull.repo.slug, pull.pull.number
        given = actinputs.Settings(
            identity=identity(), authors=[identity()], max_lines=limit
        )
        raw = dict(members(read(f"repos/{repo}/pulls/{number}")))
        inputs = actinputs.live_inputs(read, given)(repo, number, raw, [])
        return pullstate.gate_of(raw, {**inputs, "holds": holds_of(read, repo)})

    return gated


def identity_of(github: ghapi.GitHub) -> str:
    """The login ``gh`` is signed in as.

    Args:
        github: the reading runner.

    Returns:
        The login.
    """
    return name_at(json.loads(github.run(["gh", "api", "user"]).stdout), "login")
