"""GitHub for the act verbs' tests: the state they read and every write they make."""

import copy
import dataclasses
import json
import functools
import pathlib
import subprocess
from typing import Callable, Mapping, MutableMapping, MutableSequence, Protocol
from typing import Sequence

from .. import gateinputs
from ..actcore import Act, Controls, Decisions, Owner, Questions
from ..actport import Change, Hub, Pull
from ..totaljson import members, records
from . import totalworld
from .fakes import write

Key = tuple[str, int]


class Deciders(Protocol):
    """How a verb's decisions are made over a hub, bound to the kit."""

    def __call__(self, *, name: str, acts: MutableSequence[Act]) -> Decisions:
        """The decisions of a world's PR.

        Args:
            name: the world's PR, ``owner/name#number``.
            acts: the verb's world, once it is made (its one entry).

        Returns:
            The decisions, as each verb asks.
        """


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Rests:
    """What a fake GitHub's verbs rest on (``knownkit.rests_of`` makes it).

    Attributes:
        controls: the readers and the disarm.
        decided: how the verb's decisions are made.
        said: what the pre-push check says, its exit status and its output.
    """

    controls: Controls
    decided: Deciders
    said: tuple[int, str] = (0, "lint passed\nok\n")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Memory:
    """GitHub in memory: the state the fake port reads and writes.

    Attributes:
        pulls_made: each PR.
        events: each PR's timeline.
        issues_made: each issue.
        writes: every write, in order.
        identity: the login comments are posted with.
    """

    pulls_made: MutableMapping[Key, Pull] = dataclasses.field(default_factory=dict)
    events: MutableMapping[Key, MutableSequence[object]] = dataclasses.field(
        default_factory=dict
    )
    issues_made: MutableMapping[Key, Pull] = dataclasses.field(default_factory=dict)
    writes: MutableSequence[Change] = dataclasses.field(default_factory=list)
    identity: str = totalworld.ACT


def _pull(memory: Memory, repo: str, number: int) -> Pull:
    return copy.deepcopy(memory.pulls_made[(repo, number)])


def _timeline(memory: Memory, repo: str, number: int) -> Sequence[object]:
    return copy.deepcopy(memory.events.get((repo, number), []))


def _issues(memory: Memory, repo: str, label: str) -> Sequence[Pull]:
    return [
        issue
        for (where, _), issue in memory.issues_made.items()
        if where == repo
        and label in str(issue.get("labels")).split(",")
        and issue.get("state") == "open"
    ]


def _open_pulls(memory: Memory, repo: str) -> Sequence[Pull]:
    return [
        pull
        for (where, _), pull in memory.pulls_made.items()
        if where == repo and pull.get("state", "open") == "open"
    ]


def _write(memory: Memory, change: Change) -> str:
    memory.writes.append(change)
    return WRITES.get(change.kind, _nothing)(memory, change)


def port(memory: Memory) -> Hub:
    """The verbs' GitHub over the memory.

    Args:
        memory: the state.

    Returns:
        The port; each read gives a copy.
    """
    return Hub(
        pull=functools.partial(_pull, memory),
        timeline=functools.partial(_timeline, memory),
        issues=functools.partial(_issues, memory),
        open_pulls=functools.partial(_open_pulls, memory),
        write=functools.partial(_write, memory),
    )


def _nothing(memory: Memory, change: Change) -> str:
    return ""


def _events_of(memory: Memory, change: Change) -> MutableSequence[object]:
    # the timeline events written to the changed PR
    return memory.events.setdefault((change.repo, change.number), [])


def _comment(memory: Memory, change: Change) -> str:
    events = _events_of(memory, change)
    identifier = 5000 + sum(len(each) for each in memory.events.values())
    events.append(
        {
            "event": "commented",
            "id": identifier,
            "user": {"login": memory.identity},
            "body": change.fields["body"],
        }
    )
    return str(identifier)


def _new_issue(memory: Memory, change: Change) -> str:
    number = 100 + len(memory.issues_made)
    memory.issues_made[(change.repo, number)] = {
        "number": number,
        "state": "open",
        **change.fields,
    }
    return str(number)


def _set(
    updates: Callable[[Change], Mapping[str, object]], where: str = "pulls"
) -> Callable[[Memory, Change], str]:
    def made(memory: Memory, change: Change) -> str:
        table = memory.pulls_made if where == "pulls" else memory.issues_made
        table[(change.repo, change.number)].update(updates(change))
        return ""

    return made


def _labels(add: bool) -> Callable[[Memory, Change], str]:
    def made(memory: Memory, change: Change) -> str:
        pull = memory.pulls_made[(change.repo, change.number)]
        names = [
            each.get("name")
            for each in records(pull.get("labels"))
            if each.get("name") != change.fields["name"]
        ]
        pull["labels"] = [
            {"name": each}
            for each in [*names, *([change.fields["name"]] if add else [])]
        ]
        return ""

    return made


def _dequeue(memory: Memory, change: Change) -> str:
    _events_of(memory, change).append({"event": "removed_from_merge_queue"})
    return ""


def _pr(memory: Memory, change: Change) -> str:
    number = 900 + len(memory.pulls_made)
    memory.pulls_made[(change.repo, number)] = {
        "number": number,
        "state": "open",
        **change.fields,
    }
    return str(number)


WRITES: Mapping[str, Callable[[Memory, Change], str]] = {
    "comment": _comment,
    "issue": _new_issue,
    "pr": _pr,
    "issue-edit": _set(lambda change: dict(change.fields), "issues"),
    "close-issue": _set(lambda change: {"state": "closed"}, "issues"),
    "pr-edit": _set(lambda change: dict(change.fields)),
    "arm": _set(lambda change: {"auto_merge": {"merge_method": "merge"}}),
    "disarm": _set(lambda change: {"auto_merge": None}),
    "merge": _set(lambda change: {"merged": True, "state": "closed"}),
    "undraft": _set(lambda change: {"draft": False}),
    "label": _labels(True),
    "unlabel": _labels(False),
    "dequeue": _dequeue,
}


def git_run(cmdargs: Sequence[str], /) -> subprocess.CompletedProcess[str]:
    """Run a command for real, raising when it fails.

    Args:
        cmdargs: the command line.

    Returns:
        The finished process.
    """
    return subprocess.run(list(cmdargs), capture_output=True, text=True, check=True)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Made:
    """A fake GitHub holding a world, and a verb's world over it.

    Attributes:
        hub: the fake GitHub's state.
        act: the verb's world.
        world: the world it holds.
    """

    hub: Memory
    act: Act
    world: totalworld.World


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class WorldInputs:
    """The verdict's inputs: the world's, with the hub's timeline.

    Attributes:
        world: the world.
        hub: the fake GitHub.
    """

    world: totalworld.World
    hub: Hub

    def __call__(
        self, where: str, which: int, pull: Pull, timeline: Sequence[object]
    ) -> Pull:
        """The inputs of a PR.

        Args:
            where: the repository.
            which: the PR's number.
            pull: the PR, unread here.
            timeline: its timeline, when read; the hub's when empty.

        Returns:
            The inputs, with the blockers the body names (``blockers_of``).
        """
        events = timeline or self.hub.timeline(where, which)
        given = {**self.world.ctx, "timeline": events}
        return gateinputs.blockers_in(pull, given, where)


def _memory(world: totalworld.World) -> Memory:
    # the hub's state: the world's PR and its timeline
    key = (str(world.ctx["repo"]), int(str(world.pull["number"])))
    memory = Memory(pulls_made={key: copy.deepcopy(world.pull)})
    memory.events[key] = list(records(world.ctx["timeline"]))
    return memory


def holding(
    world: totalworld.World,
    given: Rests,
    owner: Owner | None = None,
    repos: Sequence[str] = (),
) -> Made:
    """A fake GitHub holding a world's PR and timeline.

    Args:
        world: the world.
        given: the controls and the gate.
        owner: the owner's messages (none when None).
        repos: the project's repositories (the world's when none).

    Returns:
        The hub and the verb's world.
    """
    memory = _memory(world)
    project = (owner or Owner(), list(repos) or [str(world.ctx["repo"])])
    act = _act(port(memory), world, given, project)
    return Made(hub=memory, act=act, world=world)


def _act(
    hub: Hub,
    world: totalworld.World,
    given: Rests,
    project: tuple[Owner, Sequence[str]],
) -> Act:
    # the verb's world over the hub (the owner's messages and the project's
    # repositories), its decisions made as ``decide`` makes them
    inputs = WorldInputs(world=world, hub=hub)
    made: list[Act] = []
    act = Act(
        hub=hub,
        inputs=inputs,
        owner=project[0],
        repos=project[1],
        p90=lambda _: 2151,
        run=git_run,
        prepush=lambda: given.said,
        questions=Questions(decided=given.decided(name=_name_of(world), acts=made)),
        controls=given.controls,
    )
    made.append(act)
    return act


def rule_checkouts(root: pathlib.Path) -> Mapping[str, pathlib.Path]:
    """The rule files of the real repositories, written as checkouts.

    Args:
        root: where to write them.

    Returns:
        Each repository's checkout.
    """
    found = json.loads(totalworld.folder_text("rulefiles.json"))
    written = {}
    for repo, files in members(found).items():
        checkout = root / repo.split("/")[1]
        for name, text in members(files).items():
            (checkout / name).parent.mkdir(parents=True, exist_ok=True)
            write(checkout / name, str(text))
        written[repo] = checkout
    return written


def _name_of(world: totalworld.World) -> str:  # the world's PR, owner/name#number
    return f"{world.ctx['repo']}#{world.ctx['number']}"
