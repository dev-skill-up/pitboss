"""The seeded faults X25 to X38 (X36 is no fault: a Plan command is run as written).

A case passes only when its control refuses the unsafe world and lets its safe
twin through; ``test_known`` runs every table.
"""

from typing import MutableMapping

from ..actcore import Target
from . import knownkit, knownplay
from .knownkit import change, stops
from .knownplay import pull_now, review_edited, stopping
from .knowngit import git, refusing_pair, repo_pair
from .totalworld import ARMED

CASES: MutableMapping[str, knownkit.Known] = {}
case = knownkit.registry(CASES)


def dispatch_target() -> Target:
    """The project's repository as a target.

    Returns:
        The target.
    """
    return Target(repo=knownkit.REPO)


@case(
    "X27",
    "verdict row; paused-owner disarms",
    "paused-owner on a PR with auto-merge armed",
)
def _paused_armed(given: knownkit.Kit) -> bool:
    armed = knownplay.arm_record()
    world = knownkit.change(
        pull={**ARMED, "labels": [{"name": "paused-owner"}]}, events=[armed]
    )
    hub = knownkit.made(given, knownkit.change(pull=ARMED, events=[armed]))
    knownkit.act(given, hub, "label", name="paused-owner")
    return (
        knownkit.stops(given, "merge", world, "auto_merge armed on a paused-owner")
        and pull_now(hub)["auto_merge"] is None
    )


@case(
    "X29",
    "ticket reader (closed world)",
    "a `Priority: p1` line after the Done-when bullets",
)
def _priority(given: knownkit.Kit) -> bool:
    return list(
        given.rests.controls.items("## Done when\n\n- a\n- b\n\nPriority: p1\n")
    ) == [
        "a",
        "b",
    ]


@case(
    "X30",
    "verdict event and base rows",
    "the base changed to `release` after the approval",
)
def _base_changed(given: knownkit.Kit) -> bool:
    base = {**knownkit.base_map("pull", "base"), "ref": "release"}
    changed = change(events=[{"event": "base_ref_changed"}])
    return stops(given, "merge", changed, "event base_ref_changed") and stops(
        given, "merge", change(pull={"base": base}), "base="
    )


@case(
    "X31",
    "a required check must be reported; not overridable",
    "a ruling says `skip the e2e run, merge when green`",
)
def _skip_e2e(given: knownkit.Kit) -> bool:
    required = [*knownkit.base_items("required_checks"), "e2e"]
    world = knownkit.change(ctx={"required_checks": required})
    lines = [
        each
        for each in knownkit.verdict(given, "merge", world).lines
        if each.startswith("check e2e")
    ]
    return bool(lines) and bool(
        knownkit.refused(
            lambda: knownkit.act(
                given,
                knownkit.made(given, world),
                "override",
                stop=lines[0],
                reason="Opus ruling: skip the e2e run",
            )
        )
    )


@case(
    "X32",
    "body row: Blocked line",
    "the body says `Blocked by owner/lib#4`, an open PR",
)
def _blocked_line(given: knownkit.Kit) -> bool:
    body = knownkit.BODY + "\nBlocked by owner/lib#4\n"
    opened = change(pull={"body": body}, ctx={"blockers": {"owner/lib#4": "open"}})
    alone = change(pull={"body": body})
    return all(
        stops(given, "merge", each, "body: blocked by") for each in (opened, alone)
    )


@case("X34", "act push: read back", "the origin refuses the push")
def _origin_refuses(given: knownkit.Kit) -> bool:
    return "not pushed" in knownkit.refused(
        lambda: knownkit.pushed(given, refusing_pair())
    )


@case(
    "X35",
    "act clean: a commit on no remote branch is kept",
    "a finished worktree with an unpushed commit removed",
)
def _kept(given: knownkit.Kit) -> bool:
    worktree = repo_pair()
    options = {"worktree": str(worktree)}
    hub = knownkit.made(given)
    kept = knownkit.refused(
        lambda: given.verbs["clean"](hub.act, dispatch_target(), options)
    )
    knownkit.pushed(given, worktree)
    git(worktree, "fetch", "-q", "origin")
    return (
        "KEPT" in kept
        and given.verbs["clean"](hub.act, dispatch_target(), options) == "removable"
    )


@case(
    "X37",
    "brief: every rule file on the ticket's paths",
    "the brief lacks the repository's setup step",
)
def _setup(given: knownkit.Kit) -> bool:
    text = knownplay.brief_text(given, "bats", "src/helpers.bats")
    return (
        "make -C /tmp/seed debug/bats" in text
        and "dist/debug/bats check --repository" in text
    )


@case(
    "X38",
    "body row: no Plan command names a machine path",
    "a Plan row `rm -rf` of the shared cache under the home directory",
)
def _home_path(given: knownkit.Kit) -> bool:
    bad = knownplay.plan_row("| 9 | `rm -rf ~/.cache/bats` | exits 0 |")
    edit = knownplay.edit_refused(given, bad)
    named = stops(given, "merge", change(pull={"body": bad}), "body: names the path")
    return bad != knownkit.BODY and named and bool(edit)


QUEUE_EVENTS = [
    {"event": "added_to_merge_queue"},
    {"event": "removed_from_merge_queue"},
]
stopping(
    CASES,
    [
        (
            "X28",
            "review form (closed)",
            "`Verdict: approved.`",
            "review:",
            review_edited("Verdict: approved\n", "Verdict: approved.\n"),
        ),
        (
            "X33",
            "verdict event row (closed world)",
            "added to the merge queue, then removed, the queue run failed",
            "event removed_from_merge_queue",
            change(events=QUEUE_EVENTS),
        ),
    ],
)
