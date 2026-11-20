"""What a PR at the merge or the undraft step is gated on, read once (keyword: gate).

``readworld`` calls it for each such PR it examines, so the decision carries the
rows ``act`` ran before it merged (``gate``). The PR object, the head's runs and
its statuses are the fields of the PR's own read (``pulls``), not read again; the
inputs no field holds are read here once (``gateinputs``): the repository's rules,
the files, the tickets the body closes, the blockers and the timeline; its holds
are the world's (``holdissues``). A status GitHub answers (a 404) is kept as the
answer.
"""

import functools
import json
from typing import Sequence

from . import gatefacts, gateinputs, ghapi, pullobject, pullrecords
from . import pulls, pullstate, reviews, shapes, world
from .totaljson import name_at

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
        The reader; the login is read once, when first needed.
    """
    read = gateinputs.reader(github)
    identity = functools.cache(lambda: identity_of(github))

    def gated(
        pull: pulls.PullRead, holds: Sequence[pullrecords.Hold]
    ) -> gatefacts.Gate:
        given = gateinputs.Settings(
            identity=identity(), authors=[identity()]
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
