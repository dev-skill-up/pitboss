"""GitHub events that changed a PR with no ``pitboss act`` record (keyword: action-matrix).

promise#73: a merge made around a runner-pressure hold by a raw ``gh`` call. The
sweep reads GitHub's own events (merged, closed, labeled, ready for review, a push,
a dispatched run) and names each that has no record of ``pitboss act`` just before
it, with the event's id.
"""

import dataclasses
import datetime
import json
import pathlib
import subprocess
from typing import Sequence

from . import actions, actrun, config, ghapi, logline

UNLEDGERED = "UNLEDGERED"
WINDOW = datetime.timedelta(minutes=10)
DEFAULT_BRANCHES = frozenset({"main", "master"})
ISSUE_ACTIONS = {
    "merged": actions.Action.MERGE,
    "closed": actions.Action.CLOSE,
    "ready_for_review": actions.Action.UNDRAFT,
    "labeled": actions.Action.LABEL,
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seen:
    """One event of GitHub that changed a PR or its branch.

    Attributes:
        identifier: GitHub's id of the event.
        action: what it was.
        reference: the PR's ``owner/name#number``, empty for a push or a run.
        branch: the branch, empty for an event of a PR.
        time: when.
    """

    identifier: str
    action: actions.Action
    reference: str
    branch: str
    time: datetime.datetime


def _moment(text: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


def from_issue_events(slug: str, text: str) -> Sequence[Seen]:
    """The events of the PRs from the issue events of a repository.

    Args:
        slug: the repository's ``owner/name``.
        text: the JSON of ``repos/<slug>/issues/events``.

    Returns:
        The merges, closes, labels and undrafts of PRs; the ``closed`` event
        that goes with a ``merged`` one is the same act and is left out.
    """
    items = [each for each in json.loads(text) if "pull_request" in each["issue"]]
    merged = {
        (each["issue"]["number"], each["created_at"])
        for each in items
        if each["event"] == "merged"
    }
    return [
        Seen(
            identifier=str(each["id"]),
            action=ISSUE_ACTIONS[each["event"]],
            reference=f"{slug}#{each['issue']['number']}",
            branch="",
            time=_moment(each["created_at"]),
        )
        for each in items
        if each["event"] in ISSUE_ACTIONS
        and (each["event"] != "closed" or (each["issue"]["number"], each["created_at"]) not in merged)
    ]


def from_push_events(text: str) -> Sequence[Seen]:
    """The pushes to branches from the events of a repository.

    Args:
        text: the JSON of ``repos/<slug>/events``.

    Returns:
        A push for each ``PushEvent`` to a branch that is not main or master.
    """
    pushes = [each for each in json.loads(text) if each["type"] == "PushEvent"]
    return [
        Seen(
            identifier=str(each["id"]),
            action=actions.Action.PUSH,
            reference="",
            branch=each["payload"]["ref"].removeprefix("refs/heads/"),
            time=_moment(each["created_at"]),
        )
        for each in pushes
        if each["payload"]["ref"].removeprefix("refs/heads/") not in DEFAULT_BRANCHES
    ]


def from_runs(text: str) -> Sequence[Seen]:
    """The dispatched runs of a repository.

    Args:
        text: the JSON of ``repos/<slug>/actions/runs?event=workflow_dispatch``.

    Returns:
        A dispatch for each run.
    """
    return [
        Seen(
            identifier=str(each["id"]),
            action=actions.Action.DISPATCH,
            reference="",
            branch=each["head_branch"],
            time=_moment(each["created_at"]),
        )
        for each in json.loads(text)["workflow_runs"]
    ]


def _matches(seen: Seen, record: logline.Event) -> bool:
    words = record.what.split()
    if record.kind != actrun.KIND or words[0] != seen.action.value:
        return False
    named = seen.reference in words[1:2] if seen.reference else seen.branch in words[2:3]
    gap = seen.time - _moment(record.time)
    return named and datetime.timedelta(0) <= gap <= WINDOW


def findings(
    seen: Sequence[Seen], records: Sequence[logline.Event]
) -> Sequence[str]:
    """The events with no record.

    Args:
        seen: GitHub's events.
        records: the ledger's events.

    Returns:
        An ``UNLEDGERED`` line for each event no record of ``pitboss act`` for
        the same action and PR (or branch) came up to ten minutes before it. A
        record answers one event.
    """
    unused = list(records)
    found = []
    for each in sorted(seen, key=lambda event: event.time):
        match = next((record for record in unused if _matches(each, record)), None)
        if match is None:
            where = each.reference or each.branch
            found.append(
                f"{UNLEDGERED} event {each.identifier}: {each.action.value} of {where}"
                f" at {each.time.isoformat()} was not made by pitboss act; the matrix"
                " (actionmatrix.tsv) was not asked"
            )
        else:
            unused.remove(match)
    return found


def _read(github: ghapi.GitHub, slug: str) -> Sequence[Seen]:
    return [
        *from_issue_events(slug, ghapi.get(github, f"repos/{slug}/issues/events")),
        *from_push_events(ghapi.get(github, f"repos/{slug}/events")),
        *from_runs(
            ghapi.get(
                github, f"repos/{slug}/actions/runs?event=workflow_dispatch"
            )
        ),
    ]


def lines(
    github: ghapi.GitHub,
    settings: config.Config,
    log: pathlib.Path,
    since: datetime.datetime,
) -> Sequence[str]:
    """The ``UNLEDGERED`` lines of the configured repositories.

    Args:
        github: the API.
        settings: the configuration.
        log: the slot log, beside which the ledger's events are.
        since: events before it are not judged (the ledger may not go back).

    Returns:
        The lines; one line says a repository could not be read.
    """
    records = logline.read(log)
    found: list[str] = []
    for repo in config.repositories(settings):
        try:
            seen = [each for each in _read(github, repo.slug) if each.time >= since]
        except subprocess.CalledProcessError:
            found.append(f"{UNLEDGERED} {repo.slug}: its events could not be read")
            continue
        found += findings(seen, records)
    return found
