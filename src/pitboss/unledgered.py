"""GitHub events that changed a PR with no ``pitboss act`` record.

Seen on promise#73 (keyword: action-matrix): a merge made around a runner-pressure
hold by a raw ``gh`` call. The sweep reads GitHub's own events (merged, closed,
labeled, ready for review, a push, a dispatched run) and names each that has no
record of ``pitboss act`` just before it, with the event's id.
"""

import dataclasses
import datetime
import json
import pathlib
import subprocess
from typing import Callable, Mapping, Sequence, TypedDict

from . import actions, actrun, config, configrepos, ghapi, logline

UNLEDGERED = "UNLEDGERED"
WINDOW = datetime.timedelta(minutes=10)
DEFAULT_BRANCHES = frozenset({"main", "master"})
ISSUE_ACTIONS = {
    "merged": actions.Action.MERGE,
    "closed": actions.Action.CLOSE,
    "ready_for_review": actions.Action.UNDRAFT,
    "labeled": actions.Action.LABEL,
    "auto_merge_enabled": actions.Action.ARM,  # keyword: action-gates (quire#1110)
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seen:
    """One event of GitHub that changed a PR or its branch.

    Attributes:
        identifier: GitHub's id of the event.
        action: what it was.
        repository: its repository's ``owner/name``.
        reference: the PR's ``owner/name#number``, empty for a push or a run.
        branch: the branch, empty for an event of a PR.
        time: when.
    """

    identifier: str
    action: actions.Action
    repository: str
    reference: str
    branch: str
    time: datetime.datetime


def _moment(text: str) -> datetime.datetime:
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")


def _base(slug: str, each: Mapping[str, object], action: actions.Action) -> Seen:
    # what every event has; the PR or the branch is set by the caller
    return Seen(
        identifier=str(each["id"]),
        action=action,
        repository=slug,
        reference="",
        branch="",
        time=_moment(str(each["created_at"])),
    )


class IssueRef(TypedDict):
    """The issue of an event: only its number is read.

    Attributes:
        number: the number of the issue or PR.
    """

    number: int


class IssueEvent(TypedDict):
    """An event of ``issues/events``: the fields that are read.

    Attributes:
        id: GitHub's id of the event.
        event: its name (``merged``, ``closed``, ``labeled``, ...).
        created_at: when, in UTC (ISO).
        issue: the issue or PR it is on.
    """

    id: int
    event: str
    created_at: str
    issue: IssueRef


def _issue_event(slug: str, each: IssueEvent) -> Seen:
    named = f"{slug}#{each['issue']['number']}"
    base = _base(slug, each, ISSUE_ACTIONS[each["event"]])
    return dataclasses.replace(base, reference=named)


def from_issue_events(slug: str, text: str) -> Sequence[Seen]:
    """The events of the PRs from the issue events of a repository.

    Args:
        slug: the repository's ``owner/name``.
        text: the JSON of ``repos/<slug>/issues/events``.

    Returns:
        The merges, closes, labels and undrafts of PRs; the ``closed`` event
        that goes with a ``merged`` one is the same act and is left out.
    """
    items = [
        each
        for each in json.loads(text)
        if "pull_request" in each["issue"] and each["event"] in ISSUE_ACTIONS
    ]
    merged = {
        (each["issue"]["number"], each["created_at"])
        for each in items
        if ISSUE_ACTIONS[each["event"]] is actions.Action.MERGE
    }
    return [
        _issue_event(slug, each)
        for each in items
        if ISSUE_ACTIONS[each["event"]] is not actions.Action.CLOSE
        or (each["issue"]["number"], each["created_at"]) not in merged
    ]


def _branch(each: Mapping[str, Mapping[str, str]]) -> str:
    return each["payload"]["ref"].removeprefix("refs/heads/")


def from_push_events(slug: str, text: str) -> Sequence[Seen]:
    """The pushes to branches from the events of a repository.

    Args:
        slug: the repository's ``owner/name``.
        text: the JSON of ``repos/<slug>/events``.

    Returns:
        A push for each ``PushEvent`` to a branch that is not main or master.
    """
    pushes = [each for each in json.loads(text) if each["type"] == "PushEvent"]
    return [
        dataclasses.replace(
            _base(slug, each, actions.Action.PUSH), branch=_branch(each)
        )
        for each in pushes
        if _branch(each) not in DEFAULT_BRANCHES
    ]


def from_runs(slug: str, text: str) -> Sequence[Seen]:
    """The dispatched runs of a repository.

    Args:
        slug: the repository's ``owner/name``.
        text: the JSON of ``repos/<slug>/actions/runs?event=workflow_dispatch``.

    Returns:
        A dispatch for each run.
    """
    return [
        dataclasses.replace(
            _base(slug, each, actions.Action.DISPATCH), branch=each["head_branch"]
        )
        for each in json.loads(text)["workflow_runs"]
    ]


def _named(seen: Seen, words: Sequence[str]) -> bool:
    # a PR's event names the PR; a push or a run names the repository and branch
    if seen.reference:
        return seen.reference == words[1]
    return (seen.repository, seen.branch) == (words[1].partition("#")[0], words[2])


def _matches(seen: Seen, record: logline.Event) -> bool:
    words = record.what.split()
    if record.kind != actrun.KIND or words[0] != actions.word(seen.action):
        return False
    gap = seen.time - _moment(record.time)
    return _named(seen, words) and datetime.timedelta(0) <= gap <= WINDOW


def _line(each: Seen) -> str:
    where = each.reference or f"{each.repository} branch {each.branch}"
    return (
        f"{UNLEDGERED} event {each.identifier}: {actions.word(each.action)}"
        f" of {where} at {each.time.isoformat()} was not made by pitboss act; the"
        " matrix (actionmatrix.tsv) was not asked"
    )


def findings(seen: Sequence[Seen], records: Sequence[logline.Event]) -> Sequence[str]:
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
            found.append(_line(each))
        else:
            unused.remove(match)
    return found


READS: Sequence[tuple[str, Callable[[str, str], Sequence[Seen]]]] = (
    ("issues/events", from_issue_events),
    ("events", from_push_events),
    ("actions/runs?event=workflow_dispatch", from_runs),
)


def _read(github: ghapi.GitHub, slug: str) -> Sequence[Seen]:
    return [
        each
        for path, reader in READS
        for each in reader(slug, ghapi.get(github, f"repos/{slug}/{path}"))
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
    for repo in configrepos.repositories(settings):
        try:
            seen = [each for each in _read(github, repo.slug) if each.time >= since]
        except subprocess.CalledProcessError:
            found.append(f"{UNLEDGERED} {repo.slug}: its events could not be read")
            continue
        found += findings(seen, records)
    return found
