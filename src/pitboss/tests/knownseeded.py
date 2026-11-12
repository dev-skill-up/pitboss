"""The seeded faults S01 to S24, each a world run through its control.

A case passes only when its control refuses the unsafe world and lets its safe
twin through; ``test_known`` runs every table.
"""

import re
from typing import Callable

from .. import enumeration
from ..totalroutes import instructions
from . import fakehub
from .knownkit import (
    Known,
    BASE,
    BODY,
    NUMBER,
    REPO,
    Kit,
    act,
    brief,
    change,
    dispatch,
    draft,
    goes,
    made,
    refused,
    registry,
    stops,
)
from .totalworld import item, review

CASES: dict[str, Known] = {}
case = registry(CASES)


TICKET = "## Done when\n\n- x demonstrated by y\n\nPaths: src/\n"


def _routed_verbs() -> set[str]:
    rows = [
        line.split("\t")
        for line in enumeration.lines_of(enumeration.shipped("act-routes.tsv"))
        if line.count("\t") == 2
    ]
    found = {
        verb
        for row in rows
        if not row[0].startswith("class")
        for verb in re.findall(r"\bact ([a-z]+(?:-[a-z]+)*)", row[2])
    }
    return found - {"line"}


def _relock(names: list[str]) -> object:
    files = [
        {"filename": name, "status": "modified", "additions": 1, "deletions": 1}
        for name in names
    ]
    head = {**dict(BASE.pull["head"]), "ref": "relock/2026-11-01"}  # type: ignore[call-overload]
    first = list(BASE.ctx["timeline"])[:1]  # type: ignore[call-overload]
    return change(
        pull={"head": head}, ctx={"files": files, "tickets": {}, "timeline": first}
    )


KEYWORDS = (
    "close",
    "closes",
    "closed",
    "fix",
    "fixes",
    "fixed",
    "resolve",
    "resolves",
    "resolved",
    "Resolves",
)


def _with_ticket(given: Kit, body: str = BODY) -> Callable[[], str]:
    hub = made(given, change(pull={"body": body}))
    hub.hub.issues_made[(REPO, 9)] = {
        "number": 9,
        "state": "open",
        "body": TICKET,
        "labels": "",
    }
    return lambda: act(given, hub, "ticket-edit", number="9", body=TICKET)


@case("S01", "verdict event row", "renamed to `WIP: do not merge` after the approval")
def _renamed(given: Kit) -> bool:
    return stops(
        given,
        "merge",
        change(pull={"title": "WIP: do not merge"}, events=[{"event": "renamed"}]),
        "event renamed",
    )


@case(
    "S02", "verdict event row (benign by a row)", "an `unpinned` event in the timeline"
)
def _unpinned(given: Kit) -> bool:
    return goes(given, "merge", change(events=[{"event": "unpinned"}])) and stops(
        given, "merge", change(events=[{"event": "closed"}]), "event closed"
    )


@case(
    "S03",
    "verdict event row (benign by a row)",
    "an event with no created_at and a null actor",
)
def _no_actor(given: Kit) -> bool:
    return goes(
        given,
        "merge",
        change(events=[{"event": "deployment_environment_changed", "actor": None}]),
    )


@case("S04", "verdict review row on undraft", "undraft before the Plan is approved")
def _early_undraft(given: Kit) -> bool:
    world = draft({"timeline": list(BASE.ctx["timeline"])[:1]})  # type: ignore[call-overload]
    hub = made(given, world)
    return (
        stops(given, "undraft", world, "review:")
        and bool(refused(lambda: act(given, hub, "undraft")))
        and hub.hub.pull(REPO, NUMBER)["draft"] is True
    )


@case(
    "S05",
    "instructions name the act verb for every write; the verb exists",
    "`gh pr merge` by habit, outside pitboss",
)
def _habit(given: Kit) -> bool:
    text = instructions(given.requirements)
    verbs = _routed_verbs()
    named = all(
        each in text and each in given.verbs
        for each in verbs
        if each not in ("comment-edit", "scratch-clean")
    )
    return (
        "Every write to GitHub is a `pitboss act` verb" in text
        and "merge" in verbs
        and named
    )


@case(
    "S06",
    "verdict ticket row (a failed read stops)",
    "the ticket was converted to a discussion: 404",
)
def _discussion(given: Kit) -> bool:
    return stops(
        given,
        "merge",
        change(ctx={"tickets": {f"{REPO}#1": {"_error": "HTTP 404"}}}),
        "ticket ",
    )


@case("S07", "verdict typed field row", "diff_url is null")
def _diff_url(given: Kit) -> bool:
    return stops(given, "merge", change(pull={"diff_url": None}), "diff_url=")


@case("S08", "verdict field row", "the `url` names another repository")
def _url(given: Kit) -> bool:
    return stops(
        given,
        "merge",
        change(pull={"url": "https://api.github.com/repos/owner/lib/pulls/3"}),
        "url=",
    )


@case("S09", "verdict field row", "the conversation is locked")
def _locked(given: Kit) -> bool:
    return stops(
        given,
        "merge",
        change(pull={"locked": True, "active_lock_reason": "too heated"}),
        "locked=",
    )


@case("S10", "verdict label row (closed world)", "a `do-not-merge` label")
def _label(given: Kit) -> bool:
    return stops(
        given, "merge", change(pull={"labels": [{"name": "do-not-merge"}]}), "labels="
    )


@case("S11", "verdict field row", "listed as open, but closed and merged")
def _closed(given: Kit) -> bool:
    closed = {"state": "closed", "merged": True, "merged_at": "2026-11-12T00:00:00Z"}
    return stops(given, "merge", change(pull=closed), "state=")


@case("S12", "review binds the head", "the approval names an older head")
def _old_head(given: Kit) -> bool:
    first = list(BASE.ctx["timeline"])[0]  # type: ignore[call-overload]
    world = change(ctx={"timeline": [first, review("3" * 40, BODY, dict(BASE.ctx["tickets"]))]})  # type: ignore[call-overload]
    return stops(given, "merge", world, "review: the newest review's head line")


@case(
    "S13",
    "brief: every rule file on the ticket's paths",
    "bats's pins-check rule in the brief",
)
def _pins(given: Kit) -> bool:
    text, _ = brief(given, "bats", "src/pins_check.bats")
    other, _ = brief(given, "bats", "src/lexer.bats")
    return (
        "rules/pins-check.md sha256" in text
        and "rules/pins-check.md sha256" not in other
    )


@case(
    "S14",
    "brief: every rule file on the ticket's paths",
    "quire's platform rule in the brief",
)
def _platform(given: Kit) -> bool:
    return "rules/platform.md sha256" in brief(given, "quire", "src/platform.bats")[0]


@case(
    "S15",
    "brief: every rule file on the ticket's paths",
    "pwa's static-pages rule in the brief",
)
def _pages(given: Kit) -> bool:
    name = "rules/static-pages.md sha256"
    return (
        name in brief(given, "pwa", "src/static_pages.bats")[0]
        and name not in brief(given, "pwa", "src/lib.bats")[0]
    )


@case(
    "S16",
    "dispatch: a shared red is one ticket",
    "three PRs red on one check with the same failing step",
)
def _one_cause(given: Kit) -> bool:
    items = [
        item(f"rp#{n}", f"2026-11-0{n}", red_check="canonical-files", red_step="Audit")
        for n in (1, 2, 3)
    ]
    filed = [
        item(
            f"rp#{n}",
            f"2026-11-0{n}",
            red_check="canonical-files",
            red_step="Audit",
            cause_ticket="rp#700",
        )
        for n in (1, 2, 3)
    ]
    hub = made(given)
    return (
        bool(refused(lambda: dispatch(given, hub, fakehub.state(items=items))))
        and dispatch(given, hub, fakehub.state(items=filed)) == "rp#1"
    )


@case(
    "S17",
    "dispatch: a red of the base is not the PR's",
    "the PR is red on tools-test, and so is main",
)
def _base_red(given: Kit) -> bool:
    items = [item("rp#3", "2026-11-01", red_check="tools-test", red_step="Test")]
    hub = made(given)
    red = fakehub.state(items=items, base_red=["tools-test"])
    return (
        bool(refused(lambda: dispatch(given, hub, red)))
        and dispatch(given, hub, fakehub.state(items=items)) == "rp#3"
    )


@case(
    "S18", "verdict status row", "approved, checks green, the `text-lint` status failed"
)
def _text_lint(given: Kit) -> bool:
    return stops(
        given,
        "merge",
        change(ctx={"statuses": [{"context": "text-lint", "state": "failure"}]}),
        "status text-lint",
    )


@case(
    "S19",
    "dispatch: a refused plan-check goes to its own worker",
    "the fix sent to a new worker",
)
def _own_worker(given: Kit) -> bool:
    state = fakehub.state(
        items=[item("q#3", "2026-11-01", step="plan-check-fix", worker="agent-a")]
    )
    hub = made(given)
    return (
        bool(refused(lambda: dispatch(given, hub, state, agent="agent-b")))
        and dispatch(given, hub, state, agent="agent-a") == "q#3"
    )


@case(
    "S20",
    "verdict: a relock is its files",
    "a relock PR that also changes a test file, with no review",
)
def _relock_files(given: Kit) -> bool:
    mixed, pure = _relock([".github/bats-version", "e2e/reader.spec.ts"]), _relock(
        [".github/bats-version", "bats.lock"]
    )
    return stops(given, "merge", mixed, "review:") and goes(given, "merge", pure)


@case(
    "S21",
    "a started ticket gets nothing added (GitHub's closing keywords)",
    "a case posted to a ticket that a PR `Resolves`",
)
def _started(given: Kit) -> bool:
    each = [
        refused(_with_ticket(given, f"{word} {REPO}#9\n\n" + BODY)) for word in KEYWORDS
    ]
    return all(each) and not refused(_with_ticket(given))


@case("S22", "hold record + act gate", "a label during a runner-pressure hold")
def _label_held(given: Kit) -> bool:
    hub = made(given)
    act(given, hub, "hold", number="0", scope="ci", source="m1")
    return bool(refused(lambda: act(given, hub, "label", name="p1"))) and not refused(
        lambda: act(given, made(given), "label", name="p1")
    )


@case(
    "S23",
    "review binds the body digest; act gate",
    "merge of a PR whose Plan was edited after the approval",
)
def _edited(given: Kit) -> bool:
    hub = made(given, change(pull={"body": BODY + "\nedited"}))
    return bool(refused(lambda: act(given, hub, "merge"))) and not hub.hub.pull(
        REPO, NUMBER
    ).get("merged")


@case("S24", "hold record + act gate", "workflow runs dispatched during the hold")
def _dispatch_held(given: Kit) -> bool:
    hub = made(given)
    act(given, hub, "hold", number="0", scope="ci", source="m1")
    held = refused(
        lambda: act(
            given, hub, "dispatch-workflow", number="0", workflow="check.yml", ref="b"
        )
    )
    return bool(held) and not refused(
        lambda: act(
            given,
            made(given),
            "dispatch-workflow",
            number="0",
            workflow="check.yml",
            ref="b",
        )
    )
