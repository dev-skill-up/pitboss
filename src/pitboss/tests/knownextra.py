"""The seeded faults X25 to X38 (X36 is no fault: a Plan command is run as written).

A case passes only when its control refuses the unsafe world and lets its safe
twin through; ``test_known`` runs every table.
"""

from ..actcore import Owner, Target
from . import fakehub
from .knowngit import git, repo_pair
from .knownkit import (
    Known,
    BASE,
    BODY,
    HEAD,
    NUMBER,
    REPO,
    Kit,
    act,
    brief,
    change,
    dispatch,
    made,
    pushed,
    refused,
    registry,
    review_with,
    stops,
    verdict,
)

from .totalworld import ARMED, record

CASES: dict[str, Known] = {}
case = registry(CASES)


def dispatch_target() -> Target:
    """The project's repository as a target.

    Returns:
        The target.
    """
    return Target(repo=REPO)


@case(
    "X25",
    "owner message gate; dispatch cap",
    "the cap is 2 in a ruling and 3 in the config",
)
def _cap_ruled(given: Kit) -> bool:
    hub = made(given, owner=Owner(messages=["m-cap"]))
    three = fakehub.state(
        cap=3, slots=["a", "b", "c"], ledger={"a": "x", "b": "y", "c": ""}
    )
    first = refused(lambda: dispatch(given, hub, three))
    act(given, hub, "ack", message="m-cap", kind="cap", cap="2")
    return "owner message" in first and bool(
        refused(lambda: dispatch(given, hub, three))
    )


@case(
    "X26",
    "dispatch: slots are the config's (closed world)",
    "a ledger slot the config does not name",
)
def _stray_slot(given: Kit) -> bool:
    return bool(
        refused(
            lambda: dispatch(
                given,
                made(given),
                fakehub.state(ledger={"sonnet-1": "", "old": "agent-z"}),
            )
        )
    )


@case(
    "X27",
    "verdict row; paused-owner disarms",
    "paused-owner on a PR with auto-merge armed",
)
def _paused_armed(given: Kit) -> bool:
    armed = record(f"arm head={HEAD}")
    world = change(pull={**ARMED, "labels": [{"name": "paused-owner"}]}, events=[armed])
    hub = made(given, change(pull=ARMED, events=[armed]))
    act(given, hub, "label", name="paused-owner")
    return (
        stops(given, "merge", world, "auto_merge armed on a paused-owner")
        and hub.act.hub.pull(REPO, NUMBER)["auto_merge"] is None
    )


@case("X28", "review form (closed)", "`Verdict: approved.`")
def _verdict_dot(given: Kit) -> bool:
    return stops(
        given,
        "merge",
        change(
            events=[
                review_with(
                    lambda text: text.replace(
                        "Verdict: approved\n", "Verdict: approved.\n"
                    )
                )
            ]
        ),
        "review:",
    )


@case(
    "X29",
    "ticket reader (closed world)",
    "a `Priority: p1` line after the Done-when bullets",
)
def _priority(given: Kit) -> bool:
    return list(given.controls.items("## Done when\n\n- a\n- b\n\nPriority: p1\n")) == [
        "a",
        "b",
    ]


@case(
    "X30",
    "verdict event and base rows",
    "the base changed to `release` after the approval",
)
def _base_changed(given: Kit) -> bool:
    base = {**dict(BASE.pull["base"]), "ref": "release"}  # type: ignore[call-overload]
    return stops(
        given,
        "merge",
        change(events=[{"event": "base_ref_changed"}]),
        "event base_ref_changed",
    ) and stops(given, "merge", change(pull={"base": base}), "base=")


@case(
    "X31",
    "a required check must be reported; not overridable",
    "a ruling says `skip the e2e run, merge when green`",
)
def _skip_e2e(given: Kit) -> bool:
    world = change(ctx={"required_checks": [*list(BASE.ctx["required_checks"]), "e2e"]})  # type: ignore[call-overload]
    lines = [
        each
        for each in verdict(given, "merge", world).lines
        if each.startswith("check e2e")
    ]
    return bool(lines) and bool(
        refused(
            lambda: act(
                given,
                made(given, world),
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
def _blocked_line(given: Kit) -> bool:
    body = BODY + "\nBlocked by owner/lib#4\n"
    opened = change(pull={"body": body}, ctx={"blockers": {"owner/lib#4": "open"}})
    return stops(given, "merge", opened, "body: blocked by") and stops(
        given, "merge", change(pull={"body": body}), "body: blocked by"
    )


@case(
    "X33",
    "verdict event row (closed world)",
    "added to the merge queue, then removed, the queue run failed",
)
def _queue_failed(given: Kit) -> bool:
    events = [{"event": "added_to_merge_queue"}, {"event": "removed_from_merge_queue"}]
    return stops(
        given, "merge", change(events=events), "event removed_from_merge_queue"
    )


@case("X34", "act push: read back", "the origin refuses the push")
def _origin_refuses(given: Kit) -> bool:
    return "not pushed" in refused(lambda: pushed(given, repo_pair(refuse=True)))


@case(
    "X35",
    "act clean: a commit on no remote branch is kept",
    "a finished worktree with an unpushed commit removed",
)
def _kept(given: Kit) -> bool:
    worktree = repo_pair()
    options = {"worktree": str(worktree)}
    hub = made(given)
    kept = refused(lambda: given.verbs["clean"](hub.act, dispatch_target(), options))
    pushed(given, worktree)
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
def _setup(given: Kit) -> bool:
    text, _ = brief(given, "bats", "src/helpers.bats")
    return (
        "make -C /tmp/seed debug/bats" in text
        and "dist/debug/bats check --repository" in text
    )


@case(
    "X38",
    "body row: no Plan command names a machine path",
    "a Plan row `rm -rf` of the shared cache under the home directory",
)
def _home_path(given: Kit) -> bool:
    bad = BODY.replace(
        "## Plan\n", "## Plan\n\n| 9 | `rm -rf ~/.cache/bats` | exits 0 |\n", 1
    )
    edit = refused(lambda: act(given, made(given), "pr-edit", body=bad))
    return (
        bad != BODY
        and stops(given, "merge", change(pull={"body": bad}), "body: names the path")
        and bool(edit)
    )
