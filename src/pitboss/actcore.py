"""``pitboss act``: the one path for every write to GitHub (pitboss#444).

The keyword is act-verbs. A verb reads the state, runs the verdict, writes, and reads
back; the agent gives only the intent. Every verb that changes GitHub first
passes the owner gate (an owner message with no disposition refuses it) and the
hold gate (a hold whose scope covers the verb refuses it). The invariant "armed
means GO": a verb that changes an input of the verdict on an armed PR disarms it
first. GitHub is a port (``Hub``) with one write (``Change``), so the verbs run
the same against GitHub (``acthub``) and against a test's fake.
"""

import dataclasses
import re
from typing import Callable, Mapping, Sequence

from . import actport, actstands, answer, ticketreader, totaljson
from .running import Run
from .totaljson import JsonMap, name_at, text

Pull = actport.Pull
Options = actport.Options
option = actport.option
options_of = actport.options_of
HOLD_LABEL = "pitboss-hold"
ACK_LABEL = "pitboss-ack"
RECORD = "pitboss-act:"
HELD = actport.HELD
ENDS_A_HOLD = actport.ENDS_A_HOLD
DISARMING = frozenset({"all", "merges", "ci"})
EVERY_REPOSITORY = frozenset({"", "all"})
QUEUED = "added_to_merge_queue"
QUEUE_EVENTS = frozenset({QUEUED, "removed_from_merge_queue"})


Refused = actport.Refused
Stood = Sequence[actstands.Stands]  # what stands instead of a write, if anything
Change = actport.Change
Hub = actport.Hub
Target = actport.Target


Owner = actport.Owner
cap_of = actport.cap_of


Inputs = Callable[[str, int, Pull, Sequence[object]], Pull]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Controls:
    """What the verbs rest on (each can be given, so a test can take one out).

    Attributes:
        owner_gate: the owner gate.
        hold_gate: the hold gate.
        disarm: what disarms an armed PR before its inputs change.
        items: the ticket reader.
        started: which open PRs close a ticket.
    """

    owner_gate: Callable[["Act"], Stood] = lambda act: owner_gate(act)
    hold_gate: Callable[["Act", str, str], Stood] = lambda act, verb, repo: hold_gate(
        act, verb, repo
    )
    disarm: Callable[["Act", Target, str], None] = (
        lambda act, target, why: disarm_if_armed(act, target, why)
    )
    items: ticketreader.Reader = ticketreader.items
    started: Callable[[Sequence[tuple[int, str | None]], str, int], Sequence[int]] = (
        ticketreader.started
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Questions:
    """What the verbs ask of the decisions, reading the world once.

    Attributes:
        decided: the decisions of the one read of the command line's mode:
            ``dispatch-next`` looks the head of the order up in them, and merge,
            arm, undraft and override the item their mode names (keyword: gate, P8).
    """

    decided: Callable[[], answer.Decided]


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
        controls: the gates and readers.
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


def owner_gate(act: Act) -> Stood:
    """What stands while an owner message has no disposition.

    Args:
        act: the verb's world.

    Returns:
        Each such message, in order.
    """
    pending = [
        each for each in act.owner.messages if each not in act.owner.dispositions
    ]
    return [
        actstands.Stands(
            why=actstands.Why.OWNER_MESSAGE,
            line=f"owner message {each} has no disposition: `pitboss act ack"
            f" {each} --kind hold|cap|ruling|none`",
        )
        for each in pending
    ]


def holds(act: Act, repo: str) -> Sequence[Pull]:
    """The holds of a repository.

    Args:
        act: the verb's world.
        repo: the repository.

    Returns:
        Each hold's ``title`` and ``scope``.
    """
    found = []
    for issue in act.hub.issues(repo, HOLD_LABEL):
        scope = re.search(r"scope=(\w+)", text(issue.get("body")))
        found.append(
            {
                "title": issue.get("title"),
                "number": issue.get("number"),
                "scope": scope.group(1) if scope else "all",
            }
        )
    return found


def hold_gate(act: Act, verb: str, repo: str) -> Stood:
    """What stands when a hold covers a verb.

    Args:
        act: the verb's world.
        verb: the verb.
        repo: its repository ("" or "all" for every repository of the project).

    Returns:
        Each hold that covers it, in order.
    """
    if verb in ENDS_A_HOLD:
        return []
    return [
        actstands.Stands(
            why=actstands.Why.HOLD,
            line=f"hold: {hold['title']} holds {verb} in {each}",
        )
        for each in ([repo] if repo not in EVERY_REPOSITORY else act.repos)
        for hold in holds(act, each)
        if hold["scope"] == "all" or verb in HELD.get(text(hold["scope"]), ())
    ]


def gate(act: Act, verb: str, repo: str) -> Stood:
    """The owner gate, then the hold gate.

    Args:
        act: the verb's world.
        verb: the verb.
        repo: its repository.

    Returns:
        What stands instead of the verb, the owner gate's first.
    """
    stood = act.controls.owner_gate(act)
    return stood or act.controls.hold_gate(act, verb, repo)


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
