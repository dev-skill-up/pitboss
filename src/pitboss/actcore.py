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
from typing import AbstractSet, Callable, Mapping, MutableMapping, Sequence

from . import actport, dispatchnext, ticketreader, totalanswer, totaljson
from .running import Run
from .totaljson import JsonMap, name_at, text

Pull = actport.Pull
Options = Mapping[str, str]
HOLD_LABEL = "pitboss-hold"
ACK_LABEL = "pitboss-ack"
RECORD = "pitboss-act:"
HELD: Mapping[str, AbstractSet[str]] = {
    "pushes": frozenset({"push", "update-branch"}),
    "merges": frozenset({"merge", "arm"}),
    "undrafts": frozenset({"undraft"}),
    "ci": frozenset(
        {
            "push",
            "update-branch",
            "merge",
            "arm",
            "undraft",
            "rerun",
            "dispatch-workflow",
            "label",
            "pr-create",
        }
    ),
    "dispatch": frozenset({"dispatch-next"}),
}
ENDS_A_HOLD = frozenset(
    {
        "hold",
        "unhold",
        "ack",
        "disarm",
        "comment",
        "override",
        "block",
        "ticket",
        "review",
        "close",
    }
)
DISARMING = frozenset({"all", "merges", "ci"})
EVERY_REPOSITORY = frozenset({"", "all"})
QUEUED = "added_to_merge_queue"
QUEUE_EVENTS = frozenset({QUEUED, "removed_from_merge_queue"})


class Refused(Exception):
    """The verb does not write: a gate, the verdict or the form refused it."""


Change = actport.Change
Hub = actport.Hub
Target = actport.Target


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Owner:
    """The owner's messages and their dispositions.

    Attributes:
        messages: the ids of the owner's messages, in order.
        dispositions: each answered message's disposition (``ack`` adds one).
        caps: the caps ``ack --kind cap`` set, by message, oldest first (``ack``
            adds one).
    """

    messages: Sequence[str] = ()
    dispositions: MutableMapping[str, str] = dataclasses.field(default_factory=dict)
    caps: MutableMapping[str, int] = dataclasses.field(default_factory=dict)


def cap_of(owner: Owner) -> int:
    """The cap the owner set last.

    Args:
        owner: the owner's messages.

    Returns:
        It, or 0 for the configuration's.
    """
    return list(owner.caps.values())[-1] if owner.caps else 0


Inputs = Callable[[str, int, Pull, Sequence[object]], Pull]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Controls:
    """What the verbs rest on (each can be given, so a test can take one out).

    Attributes:
        verdict: the total verdict.
        owner_gate: the owner gate.
        hold_gate: the hold gate.
        disarm: what disarms an armed PR before its inputs change.
        items: the ticket reader.
        started: which open PRs close a ticket.
        next_item: the order of work.
        not_overridable: the starts of the stop lines no override lifts.
    """

    verdict: Callable[[str, JsonMap, JsonMap], totalanswer.Answer]
    owner_gate: Callable[["Act"], None] = lambda act: owner_gate(act)
    hold_gate: Callable[["Act", str, str], None] = lambda act, verb, repo: hold_gate(
        act, verb, repo
    )
    disarm: Callable[["Act", Target, str], None] = (
        lambda act, target, why: disarm_if_armed(act, target, why)
    )
    items: Callable[[str | None], Sequence[str]] = ticketreader.items
    started: Callable[[Sequence[tuple[int, str | None]], str, int], Sequence[int]] = (
        ticketreader.started
    )
    next_item: Callable[[dispatchnext.State, str, str], dispatchnext.Item] = (
        dispatchnext.next_item
    )
    not_overridable: Sequence[str]


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
        work: the slots, the ledger and the items the order of work reads.
        controls: the gates and readers.
    """

    hub: Hub
    inputs: Inputs
    owner: Owner
    repos: Sequence[str]
    p90: Callable[[str], int]
    run: Run
    prepush: Callable[[], tuple[int, str]]
    work: Callable[[], dispatchnext.State]
    controls: Controls


def owner_gate(act: Act) -> None:
    """Refuse while an owner message has no disposition.

    Args:
        act: the verb's world.

    Raises:
        Refused: the first such message.
    """
    pending = [
        each for each in act.owner.messages if each not in act.owner.dispositions
    ]
    if pending:
        raise Refused(
            f"owner message {pending[0]} has no disposition: `pitboss act ack"
            f" {pending[0]} --kind hold|cap|ruling|none`"
        )


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


def hold_gate(act: Act, verb: str, repo: str) -> None:
    """Refuse a verb a hold covers.

    Args:
        act: the verb's world.
        verb: the verb.
        repo: its repository ("" or "all" for every repository of the project).

    Raises:
        Refused: the first hold that covers it.
    """
    if verb in ENDS_A_HOLD:
        return
    for each in [repo] if repo not in EVERY_REPOSITORY else act.repos:
        for hold in holds(act, each):
            if hold["scope"] == "all" or verb in HELD.get(text(hold["scope"]), ()):
                raise Refused(f"hold: {hold['title']} holds {verb} in {each}")


def gate(act: Act, verb: str, repo: str) -> None:
    """The owner gate, then the hold gate.

    Args:
        act: the verb's world.
        verb: the verb.
        repo: its repository.
    """
    act.controls.owner_gate(act)
    act.controls.hold_gate(act, verb, repo)


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
    pull = act.hub.pull(target.repo, target.number)
    if pull.get("auto_merge"):
        put(act, target, "disarm")
        record(act, target, f'disarm reason="{why}"')
    if queued(act.hub.timeline(target.repo, target.number)):
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


def verdict_of(act: Act, action: str, target: Target) -> Pull:
    """Read a PR and its inputs, and run the verdict.

    Args:
        act: the verb's world.
        action: the action.
        target: the PR.

    Returns:
        The PR, when the verdict is GO.

    Raises:
        Refused: the verdict is STOP; the message carries its first lines.
    """
    pull = act.hub.pull(target.repo, target.number)
    events = act.hub.timeline(target.repo, target.number)
    ctx = {
        **act.inputs(target.repo, target.number, pull, events),
        "holds": list(holds(act, target.repo)),
    }
    answer = act.controls.verdict(action, pull, ctx)
    if answer.word != totalanswer.GO:
        raise Refused(
            f"{action} {target.repo}#{target.number}: STOP: "
            + "; ".join(answer.lines[:3])
        )
    return pull


def head_of(pull: JsonMap) -> str:
    """A PR's head commit.

    Args:
        pull: the PR.

    Returns:
        Its sha.
    """
    return name_at(pull, "head", "sha")


def option(options: Options, name: str) -> str:
    """A verb's option that must be given.

    Args:
        options: the options.
        name: the option.

    Returns:
        Its value.

    Raises:
        Refused: it is not given.
    """
    if not options.get(name):
        raise Refused(f"{name}=... is required")
    return options[name]
