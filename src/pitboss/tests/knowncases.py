"""The known gaps G1 to G14, each a world run through its control.

A case passes only when its control refuses the unsafe world and lets its safe
twin through; ``test_known`` runs every table.
"""

import copy
from typing import Mapping, MutableMapping

from .. import actcore
from ..rulecases import Case
from . import fakehub, knownkit, knownplay
from .knownkit import change, stops
from .knownplay import (
    capped,
    dispatch_refused,
    held,
    pull_now,
    refuses,
    review_edited,
    stopping,
)

from .totalworld import files_of, item, record

CASES: MutableMapping[str, knownkit.Known] = {}
case = knownkit.registry(CASES)


def _fixme(action: str, world: Mapping[str, object], everywhere: bool) -> str:
    stop = world["adds_fixme"] and (everywhere or world["repo"] != "bats-lang/quire")
    return "STOP" if stop else "GO"


@case(
    "G1",
    "dispatch: cap and slots are the config's",
    "one agent runs, cap 1, the ledger offers a second slot",
)
def _cap(given: knownkit.Kit) -> bool:
    hub = knownkit.made(given, owner=actcore.Owner(messages=["m1"]))
    first = dispatch_refused(given, hub, fakehub.state())
    capped(given, hub, "m1", "1")
    busy = fakehub.state(ledger={"sonnet-1": "agent-a"})
    wide = fakehub.state(
        slots=["sonnet-1", "sonnet-2"], ledger={"sonnet-1": "", "sonnet-2": ""}
    )
    both = dispatch_refused(given, hub, busy) and dispatch_refused(given, hub, wide)
    return (
        bool(first and both)
        and actcore.cap_of(hub.act.owner) == 1
        and knownkit.dispatch(given, hub, fakehub.state()) == "q#10"
    )


@case("G2", "hold record + act gate", "merge of an approved PR while merges are held")
def _merges_held(given: knownkit.Kit) -> bool:
    free = not knownkit.refused(
        lambda: knownkit.act(given, knownkit.made(given), "merge")
    )
    hub = knownkit.made(given)
    held(given, hub, "merges")
    return free and refuses(given, hub, "merge") and not pull_now(hub).get("merged")


@case("G3", "hold record + act gate", "undraft while undrafts are held")
def _undrafts_held(given: knownkit.Kit) -> bool:
    free = not knownkit.refused(
        lambda: knownkit.act(given, knownkit.made(given, knownkit.draft()), "undraft")
    )
    hub = knownkit.made(given, knownkit.draft())
    held(given, hub, "undrafts")
    drafted = pull_now(hub)["draft"] is True
    return free and refuses(given, hub, "undraft") and drafted


@case(
    "G4",
    "verdict diff row + recorded override",
    "a ruling allowed 4 added lines in CLAUDE.md; the gate refused them with no route",
)
def _override(given: knownkit.Kit) -> bool:
    world = knownkit.change(ctx=files_of("CLAUDE.md", 4))
    lines = [
        each
        for each in knownkit.verdict(given, "arm", world).lines
        if each.startswith("diff: CLAUDE.md")
    ]
    if not lines:
        return False
    words = (
        f'override head={knownkit.HEAD} stop="{lines[0]}" reason="ruling'
        ' repository-prototype#684"'
    )
    return knownkit.goes(
        given,
        "arm",
        knownkit.change(ctx=files_of("CLAUDE.md", 4), events=[record(words)]),
    )


@case(
    "G5",
    "verdict diff row (GitHub's own count)",
    "a blank added line counted by one version and not another",
)
def _counted(given: knownkit.Kit) -> bool:
    return knownkit.stops(
        given, "merge", knownkit.change(ctx=files_of("CLAUDE.md", 1)), "diff: CLAUDE.md"
    ) and knownkit.goes(
        given, "merge", knownkit.change(ctx=files_of("CLAUDE.md", 0, 3))
    )


@case(
    "G6",
    "review binds body and ticket digests",
    "the Plan, or the ticket's Done-when, edited after the approval",
)
def _digests(given: knownkit.Kit) -> bool:
    tickets = copy.deepcopy(knownkit.base_map("ctx", "tickets"))
    ref = next(iter(tickets))
    tickets[ref]["body"] += "- one more item\n"
    edited = knownkit.change(
        pull={"body": knownkit.BODY.replace("## Plan", "## Plan\n\nedited")}
    )
    ticket_row = "review: the newest review has no line `Ticket:"
    return stops(given, "merge", edited, "review: the body changed") and stops(
        given, "merge", change(ctx={"tickets": tickets}), ticket_row
    )


@case(
    "G8", "body row: no path outside the repository", "a Plan row names the scratchpad"
)
def _scratch_path(given: knownkit.Kit) -> bool:
    bad = knownplay.plan_row(
        "| 9 | `python3 /tmp/claude-0/x/scratchpad/canonical_check.py` | exits 0 |"
    )
    evidence = knownkit.BODY + "\n## Evidence\n\n```\n$ ls /tmp/claude-0/x\n```\n"
    null = knownplay.plan_row("| 9 | `bats check 2>/dev/null` | exits 0 |")
    edit = knownplay.edit_refused(given, bad)
    clean = not given.policy.body(
        evidence, knownkit.HEAD, {}
    ) and not given.policy.body(null, knownkit.HEAD, {})
    return (
        bad != knownkit.BODY
        and stops(given, "merge", change(pull={"body": bad}), "body: names the path")
        and bool(edit)
        and clean
    )


QUIRE_FIXME = {"repo": "bats-lang/quire", "adds_fixme": True}
OTHER_FIXME = {"repo": "bats-lang/bats", "adds_fixme": True}
C14 = [
    Case(
        name="C14", date="2026-11-12", world=OTHER_FIXME, action="merge", expect="STOP"
    ),
    Case(
        name="C14-quire",
        date="2026-11-12",
        world=QUIRE_FIXME,
        action="merge",
        expect="STOP",
    ),
]
QUIRE_E2E = Case(
    name="quire#976", date="2026-10-30", world=QUIRE_FIXME, action="merge", expect="GO"
)


@case(
    "G10",
    "rulings as cases: a conflict is a red suite",
    "`test.fixme` required by quire's rule, forbidden by C14",
)
def _rulings(given: knownkit.Kit) -> bool:
    c14, e2e = C14, QUIRE_E2E
    encodings = {
        "stop everywhere": lambda action, world: _fixme(action, world, True),
        "stop outside quire": lambda action, world: _fixme(action, world, False),
    }
    conflict = knownkit.refused(lambda: given.add(c14, e2e, encodings))
    kept = given.add(c14[:1], e2e, encodings) == "stop outside quire"
    dropped = bool(given.diff_findings(c14, c14[:1], {})) and not given.diff_findings(
        c14, [c14[0], e2e], {"C14-quire": "quire#976"}
    )
    return "C14-quire" in conflict and kept and dropped


@case(
    "G13",
    "dispatch: a shared red is one ticket",
    "three PRs red on canonical-files at the same step",
)
def _shared_red(given: knownkit.Kit) -> bool:
    items = [
        item(f"rp#{n}", f"2026-11-0{n}", red_check="canonical-files", red_step="Audit")
        for n in (1, 2, 3)
    ]
    hub = knownkit.made(given)
    one = knownkit.dispatch(given, hub, fakehub.state(items=items[:1]))
    return bool(dispatch_refused(given, hub, fakehub.state(items=items))) and (
        one == "rp#1"
    )


@case(
    "G14",
    "block record read by the verdict",
    "a PR that waits on another PR, known only to the orchestrator",
)
def _block(given: knownkit.Kit) -> bool:
    hub = knownkit.made(given)
    knownkit.act(given, hub, "block", on="bats-lang/quire#1110")
    timeline = hub.act.hub.timeline(knownkit.REPO, knownkit.NUMBER)
    world = change(ctx={"timeline": timeline})
    opened, closed = (
        change(ctx={"timeline": timeline, "blockers": {"bats-lang/quire#1110": state}})
        for state in ("open", "closed")
    )
    return (
        stops(given, "merge", opened, "blocked:")
        and stops(given, "merge", world, "blocked:")
        and knownkit.goes(given, "merge", closed)
    )


stopping(
    CASES,
    [
        (
            "G7",
            "review form (closed)",
            "`Plan: ok`",
            "review:",
            review_edited("Plan: approved", "Plan: ok"),
        ),
        (
            "G9",
            "review form (closed)",
            "a prose `Plan:` line",
            "review:",
            review_edited(
                "Plan: approved", "Plan: the plan reads fine after the revision"
            ),
        ),
        (
            "G11",
            "body row: Head line",
            "the body's Head line names an older head",
            "body: the last `Head:`",
            change(pull={"body": knownkit.BODY + "\nHead: " + "2" * 40 + "\n"}),
        ),
        (
            "G12",
            "review form (closed)",
            "`Plan: approved.`",
            "review:",
            review_edited("Plan: approved\n", "Plan: approved.\n"),
        ),
    ],
)
