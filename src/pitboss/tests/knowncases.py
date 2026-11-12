"""The known gaps G1 to G14, each a world run through its control.

A case passes only when its control refuses the unsafe world and lets its safe
twin through; ``test_known`` runs every table.
"""

import copy
from typing import Mapping

from .. import actcore, rulecases
from . import fakehub
from .knownkit import (
    Known,
    BASE,
    BODY,
    HEAD,
    NUMBER,
    REPO,
    Kit,
    act,
    change,
    dispatch,
    draft,
    goes,
    made,
    refused,
    registry,
    review_with,
    stops,
    verdict,
)

from .totalworld import files_of, item, record

CASES: dict[str, Known] = {}
case = registry(CASES)


def _fixme(action: str, world: Mapping[str, object], everywhere: bool) -> str:
    stop = world["adds_fixme"] and (everywhere or world["repo"] != "bats-lang/quire")
    return "STOP" if stop else "GO"


@case(
    "G1",
    "dispatch: cap and slots are the config's",
    "one agent runs, cap 1, the ledger offers a second slot",
)
def _cap(given: Kit) -> bool:
    hub = made(given, owner=actcore.Owner(messages=["m1"]))
    first = refused(lambda: dispatch(given, hub, fakehub.state()))
    act(given, hub, "ack", message="m1", kind="cap", cap="1")
    busy = fakehub.state(ledger={"sonnet-1": "agent-a"})
    wide = fakehub.state(
        slots=["sonnet-1", "sonnet-2"], ledger={"sonnet-1": "", "sonnet-2": ""}
    )
    both = refused(lambda: dispatch(given, hub, busy)) and refused(
        lambda: dispatch(given, hub, wide)
    )
    return (
        bool(first and both)
        and actcore.cap_of(hub.act.owner) == 1
        and dispatch(given, hub, fakehub.state()) == "q#10"
    )


@case("G2", "hold record + act gate", "merge of an approved PR while merges are held")
def _merges_held(given: Kit) -> bool:
    free = not refused(lambda: act(given, made(given), "merge"))
    hub = made(given)
    act(given, hub, "hold", number="0", scope="merges", source="m1")
    return (
        free
        and bool(refused(lambda: act(given, hub, "merge")))
        and not hub.act.hub.pull(REPO, NUMBER).get("merged")
    )


@case("G3", "hold record + act gate", "undraft while undrafts are held")
def _undrafts_held(given: Kit) -> bool:
    free = not refused(lambda: act(given, made(given, draft()), "undraft"))
    hub = made(given, draft())
    act(given, hub, "hold", number="0", scope="undrafts", source="m1")
    return (
        free
        and bool(refused(lambda: act(given, hub, "undraft")))
        and hub.act.hub.pull(REPO, NUMBER)["draft"] is True
    )


@case(
    "G4",
    "verdict diff row + recorded override",
    "a ruling allowed 4 added lines in CLAUDE.md; the gate refused them with no route",
)
def _override(given: Kit) -> bool:
    world = change(ctx=files_of("CLAUDE.md", 4))
    lines = [
        each
        for each in verdict(given, "arm", world).lines
        if each.startswith("diff: CLAUDE.md")
    ]
    if not lines:
        return False
    words = (
        f'override head={HEAD} stop="{lines[0]}" reason="ruling'
        ' repository-prototype#684"'
    )
    return goes(
        given, "arm", change(ctx=files_of("CLAUDE.md", 4), events=[record(words)])
    )


@case(
    "G5",
    "verdict diff row (GitHub's own count)",
    "a blank added line counted by one version and not another",
)
def _counted(given: Kit) -> bool:
    return stops(
        given, "merge", change(ctx=files_of("CLAUDE.md", 1)), "diff: CLAUDE.md"
    ) and goes(given, "merge", change(ctx=files_of("CLAUDE.md", 0, 3)))


@case(
    "G6",
    "review binds body and ticket digests",
    "the Plan, or the ticket's Done-when, edited after the approval",
)
def _digests(given: Kit) -> bool:
    tickets = copy.deepcopy(dict(BASE.ctx["tickets"]))  # type: ignore[call-overload]
    ref = next(iter(tickets))
    tickets[ref]["body"] += "- one more item\n"
    edited = change(pull={"body": BODY.replace("## Plan", "## Plan\n\nedited")})
    return stops(given, "merge", edited, "review: the body changed") and stops(
        given,
        "merge",
        change(ctx={"tickets": tickets}),
        "review: the newest review has no line `Ticket:",
    )


@case("G7", "review form (closed)", "`Plan: ok`")
def _plan_ok(given: Kit) -> bool:
    return stops(
        given,
        "merge",
        change(
            events=[
                review_with(lambda text: text.replace("Plan: approved", "Plan: ok"))
            ]
        ),
        "review:",
    )


@case(
    "G8", "body row: no path outside the repository", "a Plan row names the scratchpad"
)
def _scratch_path(given: Kit) -> bool:
    bad = BODY.replace(
        "## Plan\n",
        "## Plan\n\n| 9 | `python3 /tmp/claude-0/x/scratchpad/canonical_check.py` |"
        " exits 0 |\n",
        1,
    )
    evidence = BODY + "\n## Evidence\n\n```\n$ ls /tmp/claude-0/x\n```\n"
    null = BODY.replace(
        "## Plan\n", "## Plan\n\n| 9 | `bats check 2>/dev/null` | exits 0 |\n", 1
    )
    edit = refused(lambda: act(given, made(given), "pr-edit", body=bad))
    clean = not given.policy.body(evidence, HEAD, {}) and not given.policy.body(
        null, HEAD, {}
    )
    return (
        bad != BODY
        and stops(given, "merge", change(pull={"body": bad}), "body: names the path")
        and bool(edit)
        and clean
    )


@case("G9", "review form (closed)", "a prose `Plan:` line")
def _prose_plan(given: Kit) -> bool:
    prose = review_with(
        lambda text: text.replace(
            "Plan: approved", "Plan: the plan reads fine after the revision"
        )
    )
    return stops(given, "merge", change(events=[prose]), "review:")


@case(
    "G10",
    "rulings as cases: a conflict is a red suite",
    "`test.fixme` required by quire's rule, forbidden by C14",
)
def _rulings(given: Kit) -> bool:
    quire = {"repo": "bats-lang/quire", "adds_fixme": True}
    other = {"repo": "bats-lang/bats", "adds_fixme": True}
    encodings = {
        "stop everywhere": lambda action, world: _fixme(action, world, True),
        "stop outside quire": lambda action, world: _fixme(action, world, False),
    }
    c14 = [
        rulecases.Case(
            name="C14", date="2026-11-12", world=other, action="merge", expect="STOP"
        ),
        rulecases.Case(
            name="C14-quire",
            date="2026-11-12",
            world=quire,
            action="merge",
            expect="STOP",
        ),
    ]
    e2e = rulecases.Case(
        name="quire#976", date="2026-10-30", world=quire, action="merge", expect="GO"
    )
    conflict = refused(lambda: given.add(c14, e2e, encodings))
    kept = given.add(c14[:1], e2e, encodings) == "stop outside quire"
    dropped = bool(given.diff_findings(c14, c14[:1], {})) and not given.diff_findings(
        c14, [c14[0], e2e], {"C14-quire": "quire#976"}
    )
    return "C14-quire" in conflict and kept and dropped


@case("G11", "body row: Head line", "the body's Head line names an older head")
def _head_line(given: Kit) -> bool:
    return stops(
        given,
        "merge",
        change(pull={"body": BODY + "\nHead: " + "2" * 40 + "\n"}),
        "body: the last `Head:`",
    )


@case("G12", "review form (closed)", "`Plan: approved.`")
def _plan_dot(given: Kit) -> bool:
    return stops(
        given,
        "merge",
        change(
            events=[
                review_with(
                    lambda text: text.replace("Plan: approved\n", "Plan: approved.\n")
                )
            ]
        ),
        "review:",
    )


@case(
    "G13",
    "dispatch: a shared red is one ticket",
    "three PRs red on canonical-files at the same step",
)
def _shared_red(given: Kit) -> bool:
    items = [
        item(f"rp#{n}", f"2026-11-0{n}", red_check="canonical-files", red_step="Audit")
        for n in (1, 2, 3)
    ]
    hub = made(given)
    return (
        bool(refused(lambda: dispatch(given, hub, fakehub.state(items=items))))
        and dispatch(given, hub, fakehub.state(items=items[:1])) == "rp#1"
    )


@case(
    "G14",
    "block record read by the verdict",
    "a PR that waits on another PR, known only to the orchestrator",
)
def _block(given: Kit) -> bool:
    hub = made(given)
    act(given, hub, "block", on="bats-lang/quire#1110")
    timeline = hub.act.hub.timeline(REPO, NUMBER)
    world = change(ctx={"timeline": timeline})
    opened = change(
        ctx={"timeline": timeline, "blockers": {"bats-lang/quire#1110": "open"}}
    )
    closed = change(
        ctx={"timeline": timeline, "blockers": {"bats-lang/quire#1110": "closed"}}
    )
    return (
        stops(given, "merge", opened, "blocked:")
        and stops(given, "merge", world, "blocked:")
        and goes(given, "merge", closed)
    )
