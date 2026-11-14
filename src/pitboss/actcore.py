"""``pitboss act``: the one path for every write to GitHub (pitboss#444).

The keyword is act-verbs. A verb's answer is decided in the command's one read
(``actdecide``: an owner message with no disposition, a hold whose scope covers the
verb, the fact the verb turns on), and ``actverbs.run`` applies it only when that
answer is to go; the agent gives only the intent. The invariant "armed
means GO": a verb that changes an input of the verdict on an armed PR disarms it
first. GitHub is a port (``Hub``) with one write (``Change``), so the verbs run
the same against GitHub (``acthub``) and against a test's fake.
"""

import dataclasses
from typing import AbstractSet, Callable, Mapping, Sequence

from . import actport, answer, config, pullnames, pullrecords, ticketreader, totaljson
from .running import Run
from .totaljson import JsonMap, name_at, text

Pull = actport.Pull
Options = actport.Options
option = actport.option
options_of = actport.options_of
HOLD_LABEL = pullrecords.HOLD_LABEL  # the one label of a hold (keyword: hold)
ACK_LABEL = "pitboss-ack"
RECORD = "pitboss-act:"
DISARMING = frozenset({"all", "merges", "ci"})
EVERY_REPOSITORY = frozenset({"", "all"})
QUEUED = "added_to_merge_queue"
QUEUE_EVENTS = frozenset({QUEUED, "removed_from_merge_queue"})


Refused = actport.Refused
Change = actport.Change
Hub = actport.Hub
Target = actport.Target


Owner = actport.Owner
Decisions = Callable[[actport.Asked], answer.Decided]  # the decisions, as asked
cap_of = actport.cap_of


Inputs = Callable[[str, int, Pull, Sequence[object]], Pull]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Controls:
    """What the verbs rest on (each can be given, so a test can take one out).

    Attributes:
        disarm: what disarms an armed PR before its inputs change.
        items: the ticket reader.
        works_on: the tickets a PR works on, by its title, body and branch (the one
            parse, ``pullnames.names``).
    """

    disarm: Callable[["Act", Target, str], None] = (
        lambda act, target, why: disarm_if_armed(act, target, why)
    )
    items: ticketreader.Reader = ticketreader.done_when
    works_on: Callable[[str, str, str, config.Repo], AbstractSet[str]] = pullnames.names


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Questions:
    """What the verbs ask of the decisions, reading the world once.

    Attributes:
        decided: the decisions of the one read of the command line's mode, given
            the verb asked: every verb looks its answer up in them (keyword: gate,
            P8).
    """

    decided: Decisions


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Act:
    """A verb's world.

    Attributes:
        hub: GitHub.
        inputs: the verdict's other inputs, read live for a PR.
        owner: the owner's messages.
        repos: the repositories the project sweeps (for a hold of all).
        p90: each repository's 90th percentile of changed lines.
        run: the runner git goes through.
        prepush: the pre-push check (its exit status and output).
        questions: what the verbs ask of the decisions (keyword: one-path).
        controls: the readers and the disarm.
    """

    hub: Hub
    inputs: Inputs
    owner: Owner
    repos: Sequence[str]
    p90: Callable[[str], int]
    run: Run
    prepush: Callable[[], tuple[int, str]]
    questions: "Questions"
    controls: Controls


def put(
    act: Act, target: Target, kind: str, fields: Mapping[str, str] | None = None
) -> str:
    """Make one write to a PR or issue.

    Args:
        act: the verb's world.
        target: the PR or issue (its repository alone when its number is 0).
        kind: what is written.
        fields: what the write carries.

    Returns:
        What GitHub answered.
    """
    change = Change(
        kind=kind, repo=target.repo, number=target.number, fields=fields or {}
    )
    return act.hub.write(change)


def record(act: Act, target: Target, words: str) -> None:
    """Post an act record on a PR.

    Args:
        act: the verb's world.
        target: the PR.
        words: what follows ``pitboss-act:``.
    """
    put(act, target, "comment", {"body": f"{RECORD} {words}"})


def disarm_if_armed(act: Act, target: Target, why: str) -> None:
    """Disarm auto-merge on a PR before its inputs change, and take it out of the queue.

    Args:
        act: the verb's world.
        target: the PR.
        why: the reason, recorded.
    """
    pull = pull_of(act, target)
    if pull.get("auto_merge"):
        put(act, target, "disarm")
        record(act, target, f'disarm reason="{why}"')
    if queued(timeline_of(act, target)):
        put(act, target, "dequeue", {"node_id": text(pull.get("node_id"))})
        record(act, target, f'dequeue reason="{why}"')


def queued(timeline: Sequence[object]) -> bool:
    """Whether a PR is in the merge queue.

    Args:
        timeline: its events.

    Returns:
        True when its last queue event is ``added_to_merge_queue``.
    """
    kinds = [each.get("event") for each in totaljson.records(timeline)]
    events = [each for each in kinds if each in QUEUE_EVENTS]
    return bool(events) and events[-1] == QUEUED


def head_of(pull: JsonMap) -> str:
    """A PR's head commit.

    Args:
        pull: the PR.

    Returns:
        Its sha.
    """
    return name_at(pull, "head", "sha")


def pull_of(act: Act, target: Target) -> Pull:
    """Read a PR.

    Args:
        act: the verb's world.
        target: the PR.

    Returns:
        The PR as GitHub answers it.
    """
    return act.hub.pull(target.repo, target.number)


def timeline_of(act: Act, target: Target) -> Sequence[object]:
    """Read a PR's or an issue's events.

    Args:
        act: the verb's world.
        target: the PR or issue.

    Returns:
        Its events.
    """
    return act.hub.timeline(target.repo, target.number)


def disarm_first(act: Act, target: Target, why: str) -> None:
    """Disarm a PR with the controls' disarm, before an input of its verdict changes.

    Args:
        act: the verb's world.
        target: the PR.
        why: the reason, recorded.
    """
    act.controls.disarm(act, target, why)


def repo_write(act: Act, repo: str, kind: str, fields: Mapping[str, str]) -> str:
    """Make one write to a repository (no PR or issue of it).

    Args:
        act: the verb's world.
        repo: the repository.
        kind: what is written.
        fields: what the write carries.

    Returns:
        What GitHub answered.
    """
    return act.hub.write(Change(kind=kind, repo=repo, fields=fields))


def head_now(act: Act, target: Target) -> str:
    """A PR's head commit, read now.

    Args:
        act: the verb's world.
        target: the PR.

    Returns:
        Its sha.
    """
    return head_of(pull_of(act, target))


def make_hold(act: Act, where: str, scope: str, source: str) -> str:
    """Make the hold issues and disarm and dequeue what the scope covers.

    Args:
        act: the verb's world.
        where: the repository, or "all".
        scope: the scope held.
        source: the owner message it comes from.

    Returns:
        What was done.
    """
    named = act.repos if where == "all" else [where]
    for each in named:
        fields = {
            "title": f"pitboss hold: {scope}",
            "body": f"scope={scope}\nfrom={source}",
            "labels": HOLD_LABEL,
        }
        repo_write(act, each, "issue", fields)
        if scope in DISARMING:
            _disarm_all(act, each, f"hold {scope}")
    return f"hold {scope} in {', '.join(named)}"


def _disarm_all(act: Act, repo: str, why: str) -> None:
    for pull in act.hub.open_pulls(repo):
        number = pull.get("number")
        target = Target(repo=repo, number=number if isinstance(number, int) else 0)
        disarm_first(act, target, why)
