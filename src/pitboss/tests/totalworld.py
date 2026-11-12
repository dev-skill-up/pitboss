"""The GO world of the total verdict, and worlds that differ from it in one input.

The GO world is a real PR (bats-lang/quire#1090, as GitHub answered) made open,
with green checks, an open ticket and a review in pitboss's form that names its
head, body, Plan and ticket.
"""

import copy
import dataclasses
import json
import pathlib
from typing import Iterable, Mapping

from .. import bodydigest, dispatchnext, totalreview
from ..totaljson import JsonMap, members, name_at
from ..plansection import plan_section

FOLDER = pathlib.Path(__file__).with_name("total")
ACT = "moshez"
TICKET_BODY = "## Done when\n\n- x demonstrated by y\n\nPaths: src/\nMax-lines: 462\n"
CHECKS = ("check", "android / build-android", "android / smoke-test")
Pull = dict[str, object]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class World:
    """A PR and the other inputs of its verdict.

    Attributes:
        pull: the PR.
        ctx: the inputs.
    """

    pull: Pull
    ctx: Pull


INDEPENDENT = "Independent review (a separate reviewer agent, not the author) of head"
GATE_RUN = {"name": "pitboss-gate", "status": "in_progress", "conclusion": None}
STATUSES = (
    {"context": "pitboss-gate", "state": "pending"},
    {"context": "text-lint", "state": "success"},
)
OPEN_TICKET = {
    "state": "open",
    "state_reason": None,
    "locked": False,
    "body": TICKET_BODY,
}
FILE = {"filename": "src/x.bats", "status": "modified", "additions": 10, "deletions": 2}


def review(
    head: str, body: object, tickets: Mapping[str, object], grade: str = "approved"
) -> Pull:
    """A review comment in pitboss's form.

    Args:
        head: the head it names.
        body: the PR body it read.
        tickets: the tickets it read.
        grade: the Execution grade and the verdict.

    Returns:
        The timeline event.
    """
    section = plan_section(body)
    plan = [] if section is None else [f"Plan-digest: {bodydigest.digest(section)}"]
    lines = [
        f"{INDEPENDENT} {head}: {grade}",
        "Plan: approved",
        f"Execution: {grade}",
        f"Verdict: {grade}",
        f"Body: {totalreview.digest_of(body)}",
        *plan,
        *totalreview.ticket_lines(tickets),
    ]
    return {
        "event": "commented",
        "user": {"login": ACT},
        "body": "\n".join(lines) + "\n",
    }


def _pull() -> Pull:
    found = json.loads((FOLDER / "quire-1090.json").read_text(encoding="utf-8"))
    found.update(
        state="open",
        merged=False,
        merged_at=None,
        closed_at=None,
        merged_by=None,
        mergeable=True,
        mergeable_state="blocked",
        auto_merge=None,
        labels=[],
        milestone=None,
        requested_reviewers=[],
        requested_teams=[],
        draft=False,
    )
    return dict(found)


def _ctx(repo: str, number: object, head: str) -> Pull:
    runs = [
        {"name": name, "status": "completed", "conclusion": "success"}
        for name in CHECKS
    ]
    return {
        "repo": repo,
        "number": number,
        "default_branch": "main",
        "authors": {ACT, "dependabot[bot]"},
        "act_identity": ACT,
        "required_checks": [*CHECKS, "pitboss-gate"],
        "merge_queue": True,
        "check_runs": [*runs, dict(GATE_RUN)],
        "statuses": [dict(each) for each in STATUSES],
        "tickets": {f"{repo}#1": dict(OPEN_TICKET)},
        "blockers": {},
        "files": [dict(FILE)],
        "max_lines": 462,
        "holds": [],
        "timeline": [{"event": "committed", "sha": head}],
    }


def base() -> World:
    """The GO world.

    Returns:
        The PR and its inputs; merge, arm and an undraft of it as a draft are GO.
    """
    pull = _pull()
    head = name_at(pull, "head", "sha")
    ctx = _ctx(name_at(pull, "base", "repo", "full_name"), pull.get("number"), head)
    tickets = members(ctx["tickets"])
    ctx["timeline"] = [*_events(ctx), review(head, pull.get("body"), tickets)]
    return World(pull=pull, ctx=ctx)


def _events(ctx: JsonMap) -> list[object]:
    found = ctx.get("timeline")
    return list(found) if isinstance(found, list) else []


def change(
    world: World,
    pull: Mapping[str, object] | None = None,
    ctx: Mapping[str, object] | None = None,
    events: Iterable[object] = (),
) -> World:
    """A world that differs from another in the inputs named.

    Args:
        world: the world it starts from.
        pull: fields of the PR to set.
        ctx: inputs to set.
        events: timeline events to add at the end.

    Returns:
        The new world; the old one is not changed.
    """
    made = copied(world)
    made.pull.update(pull or {})
    made.ctx.update(ctx or {})
    added = list(events)
    if added:
        made.ctx["timeline"] = [*_events(made.ctx), *added]
    return made


def copied(world: World) -> World:
    """A deep copy of a world.

    Args:
        world: the world.

    Returns:
        The copy; changing it leaves the world as it was.
    """
    return World(pull=copy.deepcopy(world.pull), ctx=copy.deepcopy(world.ctx))


def head_of(world: World) -> str:
    """The head commit of a world's PR.

    Args:
        world: the world.

    Returns:
        Its head's sha.
    """
    return name_at(world.pull, "head", "sha")


def ticket_ref(world: World) -> str:
    """The one ticket the world's body closes.

    Args:
        world: the world.

    Returns:
        Its reference.
    """
    return next(iter(members(world.ctx.get("tickets"))))


def item(ref: str, created: str, **fields: str) -> dispatchnext.Item:
    """An open PR of the order of work.

    Args:
        ref: its ``owner/name#N``.
        created: when it was opened.
        **fields: its other fields.

    Returns:
        The item.
    """
    return dispatchnext.Item(ref=ref, kind="pr", created=created, **fields)


def folder_text(name: str) -> str:
    """A file of the total verdict's data folder.

    Args:
        name: the file's name.

    Returns:
        Its text.
    """
    return (FOLDER / name).read_text(encoding="utf-8")


def ticket_item(ref: str, created: str, priority: str) -> dispatchnext.Item:
    """An open ticket of the order of work.

    Args:
        ref: its ``owner/name#N``.
        created: when it was opened.
        priority: its priority label.

    Returns:
        The item.
    """
    return dispatchnext.Item(ref=ref, kind="ticket", priority=priority, created=created)


def record(words: str) -> object:
    """An act record event.

    Args:
        words: what follows ``pitboss-act:``.

    Returns:
        The event.
    """
    return {
        "event": "commented",
        "user": {"login": ACT},
        "body": f"pitboss-act: {words}",
    }


ARMED = {"auto_merge": {"merge_method": "merge"}}


def files_of(name: str, added: int, removed: int = 0) -> Mapping[str, object]:
    """The ``files`` input of one changed file.

    Args:
        name: its path.
        added: its added lines.
        removed: its removed lines.

    Returns:
        The input.
    """
    return {
        "files": [
            {
                "filename": name,
                "status": "modified",
                "additions": added,
                "deletions": removed,
            }
        ]
    }
