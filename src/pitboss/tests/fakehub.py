"""GitHub for the act verbs' tests: the state they read and every write they make."""

import copy
import json
import dataclasses
import pathlib
import subprocess
from typing import Callable, Mapping, Sequence

from .. import actcore, dispatchnext
from ..actcore import Act, Change, Controls, Owner, Pull
from ..totaljson import mapping, records
from . import totalworld
from .totalworld import World

Key = tuple[str, int]


@dataclasses.dataclass(slots=True, kw_only=True)
class FakeHub:
    """GitHub in memory.

    Attributes:
        pulls_made: each PR.
        events: each PR's timeline.
        issues_made: each issue.
        writes: every write, in order.
        identity: the login comments are posted with.
    """

    pulls_made: dict[Key, Pull] = dataclasses.field(default_factory=dict)
    events: dict[Key, list[object]] = dataclasses.field(default_factory=dict)
    issues_made: dict[Key, Pull] = dataclasses.field(default_factory=dict)
    writes: list[Change] = dataclasses.field(default_factory=list)
    identity: str = totalworld.ACT

    def pull(self, repo: str, number: int) -> Pull:
        """Read a PR.

        Args:
            repo: the repository.
            number: the PR.

        Returns:
            A copy of it.
        """
        return copy.deepcopy(self.pulls_made[(repo, number)])

    def timeline(self, repo: str, number: int) -> list[object]:
        """Read a timeline.

        Args:
            repo: the repository.
            number: the PR.

        Returns:
            A copy of it.
        """
        return copy.deepcopy(self.events.get((repo, number), []))

    def issues(self, repo: str, label: str) -> list[Pull]:
        """Read the open issues with a label.

        Args:
            repo: the repository.
            label: the label.

        Returns:
            The issues.
        """
        return [
            issue
            for (where, _), issue in self.issues_made.items()
            if where == repo
            and label in str(issue.get("labels")).split(",")
            and issue.get("state") == "open"
        ]

    def pulls(self, repo: str) -> list[Pull]:
        """Read the open PRs.

        Args:
            repo: the repository.

        Returns:
            The PRs.
        """
        return [
            pull
            for (where, _), pull in self.pulls_made.items()
            if where == repo and pull.get("state", "open") == "open"
        ]

    def write(self, change: Change) -> str:
        """Make one write.

        Args:
            change: the write.

        Returns:
            The number of what was made, or "".
        """
        self.writes.append(change)
        return WRITES.get(change.kind, _nothing)(self, change)


def _nothing(hub: FakeHub, change: Change) -> str:
    return ""


def _comment(hub: FakeHub, change: Change) -> str:
    events = hub.events.setdefault((change.repo, change.number), [])
    identifier = 5000 + sum(len(each) for each in hub.events.values())
    events.append(
        {
            "event": "commented",
            "id": identifier,
            "user": {"login": hub.identity},
            "body": change.fields["body"],
        }
    )
    return str(identifier)


def _issue(hub: FakeHub, change: Change) -> str:
    number = 100 + len(hub.issues_made)
    hub.issues_made[(change.repo, number)] = {
        "number": number,
        "state": "open",
        **change.fields,
    }
    return str(number)


def _set(
    updates: Callable[[Change], Mapping[str, object]], where: str = "pulls"
) -> Callable[[FakeHub, Change], str]:
    def made(hub: FakeHub, change: Change) -> str:
        table = hub.pulls_made if where == "pulls" else hub.issues_made
        table[(change.repo, change.number)].update(updates(change))
        return ""

    return made


def _labels(add: bool) -> Callable[[FakeHub, Change], str]:
    def made(hub: FakeHub, change: Change) -> str:
        pull = hub.pulls_made[(change.repo, change.number)]
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


def _dequeue(hub: FakeHub, change: Change) -> str:
    hub.events.setdefault((change.repo, change.number), []).append(
        {"event": "removed_from_merge_queue"}
    )
    return ""


def _pr(hub: FakeHub, change: Change) -> str:
    number = 900 + len(hub.pulls_made)
    hub.pulls_made[(change.repo, number)] = {
        "number": number,
        "state": "open",
        **change.fields,
    }
    return str(number)


WRITES: Mapping[str, Callable[[FakeHub, Change], str]] = {
    "comment": _comment,
    "issue": _issue,
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


def state(**changes: object) -> dispatchnext.State:
    """A dispatch state: one free slot of a cap of 1 and one p1 ticket.

    Args:
        **changes: the fields to set.

    Returns:
        The state.
    """
    ticket = dispatchnext.Item(
        ref="q#10", kind="ticket", priority="p1", created="2026-11-01"
    )
    made = dispatchnext.State(
        cap=1, slots=["sonnet-1"], ledger={"sonnet-1": ""}, items=[ticket]
    )
    return dataclasses.replace(made, **changes)  # type: ignore[arg-type]


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
        hub: the fake GitHub.
        act: the verb's world.
        world: the world it holds.
    """

    hub: FakeHub
    act: Act
    world: World


def made(
    world: World,
    controls: Controls,
    owner: Owner | None = None,
    repos: Sequence[str] = (),
) -> Made:
    """A fake GitHub holding a world's PR and timeline.

    Args:
        world: the world.
        controls: the gates and readers.
        owner: the owner's messages (none when None).
        repos: the project's repositories (the world's when none).

    Returns:
        The hub and the verb's world.
    """
    repo, number = str(world.ctx["repo"]), int(str(world.pull["number"]))
    hub = FakeHub(pulls_made={(repo, number): copy.deepcopy(world.pull)})
    hub.events[(repo, number)] = list(records(world.ctx["timeline"]))

    def inputs(where: str, which: int, pull: Pull, timeline: list[object]) -> Pull:
        return {
            **copy.deepcopy(world.ctx),
            "timeline": timeline or hub.timeline(where, which),
        }

    act = Act(
        hub=hub,
        inputs=inputs,
        owner=owner or Owner(),
        repos=list(repos) or [repo],
        p90={repo: 2151},
        run=git_run,
        prepush=lambda: (0, "lint passed\nok\n"),
        work=state,
        controls=controls,
    )
    return Made(hub=hub, act=act, world=world)


def rule_checkouts(root: pathlib.Path) -> Mapping[str, pathlib.Path]:
    """The rule files of the real repositories, written as checkouts.

    Args:
        root: where to write them.

    Returns:
        Each repository's checkout.
    """
    found = json.loads(
        (totalworld.FOLDER / "rulefiles.json").read_text(encoding="utf-8")
    )
    checkouts = {}
    for repo, files in mapping(found).items():
        checkout = root / repo.split("/")[1]
        for name, text in mapping(files).items():
            (checkout / name).parent.mkdir(parents=True, exist_ok=True)
            (checkout / name).write_text(str(text), encoding="utf-8")
        checkouts[repo] = checkout
    return checkouts
