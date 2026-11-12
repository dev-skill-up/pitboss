"""The seeded faults S01 to S24, each a world run through its control.

A case passes only when its control refuses the unsafe world and lets its safe
twin through; ``test_known`` runs every table.
"""

import re
from typing import Callable, MutableMapping

from .. import enumeration
from ..totalroutes import instructions
from . import fakehub, knownkit
from .totalworld import item, review

CASES: MutableMapping[str, knownkit.Known] = {}
case = knownkit.registry(CASES)


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
    head = {**knownkit.base_map("pull", "head"), "ref": "relock/2026-11-01"}
    first = knownkit.base_items("timeline")[:1]
    return knownkit.change(
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


def _with_ticket(given: knownkit.Kit, body: str = knownkit.BODY) -> Callable[[], str]:
    hub = knownkit.made(given, knownkit.change(pull={"body": body}))
    hub.hub.issues_made[(knownkit.REPO, 9)] = {
        "number": 9,
        "state": "open",
        "body": TICKET,
        "labels": "",
    }
    return lambda: knownkit.act(given, hub, "ticket-edit", number="9", body=TICKET)


@case("S01", "verdict event row", "renamed to `WIP: do not merge` after the approval")
def _renamed(given: knownkit.Kit) -> bool:
    return knownkit.stops(
        given,
        "merge",
        knownkit.change(
            pull={"title": "WIP: do not merge"}, events=[{"event": "renamed"}]
        ),
        "event renamed",
    )


@case(
    "S02", "verdict event row (benign by a row)", "an `unpinned` event in the timeline"
)
def _unpinned(given: knownkit.Kit) -> bool:
    return knownkit.goes(
        given, "merge", knownkit.change(events=[{"event": "unpinned"}])
    ) and knownkit.stops(
        given, "merge", knownkit.change(events=[{"event": "closed"}]), "event closed"
    )


@case(
    "S03",
    "verdict event row (benign by a row)",
    "an event with no created_at and a null actor",
)
def _no_actor(given: knownkit.Kit) -> bool:
    return knownkit.goes(
        given,
        "merge",
        knownkit.change(
            events=[{"event": "deployment_environment_changed", "actor": None}]
        ),
    )


@case("S04", "verdict review row on undraft", "undraft before the Plan is approved")
def _early_undraft(given: knownkit.Kit) -> bool:
    world = knownkit.draft({"timeline": knownkit.base_items("timeline")[:1]})
    hub = knownkit.made(given, world)
    return (
        knownkit.stops(given, "undraft", world, "review:")
        and bool(knownkit.refused(lambda: knownkit.act(given, hub, "undraft")))
        and hub.act.hub.pull(knownkit.REPO, knownkit.NUMBER)["draft"] is True
    )


UNROUTED = frozenset({"comment-edit", "scratch-clean"})


@case(
    "S05",
    "instructions name the act verb for every write; the verb exists",
    "`gh pr merge` by habit, outside pitboss",
)
def _habit(given: knownkit.Kit) -> bool:
    text = instructions(given.requirements)
    verbs = _routed_verbs()
    named = all(
        each in text and each in given.verbs for each in verbs if each not in UNROUTED
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
def _discussion(given: knownkit.Kit) -> bool:
    return knownkit.stops(
        given,
        "merge",
        knownkit.change(
            ctx={"tickets": {f"{knownkit.REPO}#1": {"_error": "HTTP 404"}}}
        ),
        "ticket ",
    )


@case("S07", "verdict typed field row", "diff_url is null")
def _diff_url(given: knownkit.Kit) -> bool:
    return knownkit.stops(
        given, "merge", knownkit.change(pull={"diff_url": None}), "diff_url="
    )


@case("S08", "verdict field row", "the `url` names another repository")
def _url(given: knownkit.Kit) -> bool:
    return knownkit.stops(
        given,
        "merge",
        knownkit.change(pull={"url": "https://api.github.com/repos/owner/lib/pulls/3"}),
        "url=",
    )


@case("S09", "verdict field row", "the conversation is locked")
def _locked(given: knownkit.Kit) -> bool:
    return knownkit.stops(
        given,
        "merge",
        knownkit.change(pull={"locked": True, "active_lock_reason": "too heated"}),
        "locked=",
    )


@case("S10", "verdict label row (closed world)", "a `do-not-merge` label")
def _label(given: knownkit.Kit) -> bool:
    return knownkit.stops(
        given,
        "merge",
        knownkit.change(pull={"labels": [{"name": "do-not-merge"}]}),
        "labels=",
    )


@case("S11", "verdict field row", "listed as open, but closed and merged")
def _closed(given: knownkit.Kit) -> bool:
    closed = {"state": "closed", "merged": True, "merged_at": "2026-11-12T00:00:00Z"}
    return knownkit.stops(given, "merge", knownkit.change(pull=closed), "state=")


@case("S12", "review binds the head", "the approval names an older head")
def _old_head(given: knownkit.Kit) -> bool:
    first = knownkit.base_items("timeline")[0]
    tickets = knownkit.base_map("ctx", "tickets")
    stale = review("3" * 40, knownkit.BODY, tickets)
    world = knownkit.change(ctx={"timeline": [first, stale]})
    return knownkit.stops(
        given, "merge", world, "review: the newest review's head line"
    )


@case(
    "S13",
    "brief: every rule file on the ticket's paths",
    "bats's pins-check rule in the brief",
)
def _pins(given: knownkit.Kit) -> bool:
    text, _ = knownkit.brief_for(given, "bats", "src/pins_check.bats")
    other, _ = knownkit.brief_for(given, "bats", "src/lexer.bats")
    return (
        "rules/pins-check.md sha256" in text
        and "rules/pins-check.md sha256" not in other
    )


@case(
    "S14",
    "brief: every rule file on the ticket's paths",
    "quire's platform rule in the brief",
)
def _platform(given: knownkit.Kit) -> bool:
    return (
        "rules/platform.md sha256"
        in knownkit.brief_for(given, "quire", "src/platform.bats")[0]
    )


@case(
    "S15",
    "brief: every rule file on the ticket's paths",
    "pwa's static-pages rule in the brief",
)
def _pages(given: knownkit.Kit) -> bool:
    name = "rules/static-pages.md sha256"
    return (
        name in knownkit.brief_for(given, "pwa", "src/static_pages.bats")[0]
        and name not in knownkit.brief_for(given, "pwa", "src/lib.bats")[0]
    )


@case(
    "S16",
    "dispatch: a shared red is one ticket",
    "three PRs red on one check with the same failing step",
)
def _one_cause(given: knownkit.Kit) -> bool:
    red = {"red_check": "canonical-files", "red_step": "Audit"}
    items = [item(f"rp#{n}", f"2026-11-0{n}", **red) for n in (1, 2, 3)]
    filed = [
        item(f"rp#{n}", f"2026-11-0{n}", cause_ticket="rp#700", **red)
        for n in (1, 2, 3)
    ]
    hub = knownkit.made(given)
    unfiled = knownkit.refused(
        lambda: knownkit.dispatch(given, hub, fakehub.state(items=items))
    )
    return bool(unfiled) and (
        knownkit.dispatch(given, hub, fakehub.state(items=filed)) == "rp#1"
    )


@case(
    "S17",
    "dispatch: a red of the base is not the PR's",
    "the PR is red on tools-test, and so is main",
)
def _base_red(given: knownkit.Kit) -> bool:
    items = [item("rp#3", "2026-11-01", red_check="tools-test", red_step="Test")]
    hub = knownkit.made(given)
    red = fakehub.state(items=items, base_red=["tools-test"])
    return (
        bool(knownkit.refused(lambda: knownkit.dispatch(given, hub, red)))
        and knownkit.dispatch(given, hub, fakehub.state(items=items)) == "rp#3"
    )


@case(
    "S18", "verdict status row", "approved, checks green, the `text-lint` status failed"
)
def _text_lint(given: knownkit.Kit) -> bool:
    return knownkit.stops(
        given,
        "merge",
        knownkit.change(
            ctx={"statuses": [{"context": "text-lint", "state": "failure"}]}
        ),
        "status text-lint",
    )


@case(
    "S19",
    "dispatch: a refused plan-check goes to its own worker",
    "the fix sent to a new worker",
)
def _own_worker(given: knownkit.Kit) -> bool:
    state = fakehub.state(
        items=[item("q#3", "2026-11-01", step="plan-check-fix", worker="agent-a")]
    )
    hub = knownkit.made(given)
    return (
        bool(
            knownkit.refused(
                lambda: knownkit.dispatch(given, hub, state, agent="agent-b")
            )
        )
        and knownkit.dispatch(given, hub, state, agent="agent-a") == "q#3"
    )


@case(
    "S20",
    "verdict: a relock is its files",
    "a relock PR that also changes a test file, with no review",
)
def _relock_files(given: knownkit.Kit) -> bool:
    mixed, pure = _relock([".github/bats-version", "e2e/reader.spec.ts"]), _relock(
        [".github/bats-version", "bats.lock"]
    )
    return knownkit.stops(given, "merge", mixed, "review:") and knownkit.goes(
        given, "merge", pure
    )


@case(
    "S21",
    "a started ticket gets nothing added (GitHub's closing keywords)",
    "a case posted to a ticket that a PR `Resolves`",
)
def _started(given: knownkit.Kit) -> bool:
    each = [
        knownkit.refused(
            _with_ticket(given, f"{word} {knownkit.REPO}#9\n\n" + knownkit.BODY)
        )
        for word in KEYWORDS
    ]
    return all(each) and not knownkit.refused(_with_ticket(given))


@case("S22", "hold record + act gate", "a label during a runner-pressure hold")
def _label_held(given: knownkit.Kit) -> bool:
    hub = knownkit.made(given)
    knownkit.act(given, hub, "hold", number="0", scope="ci", source="m1")
    return bool(
        knownkit.refused(lambda: knownkit.act(given, hub, "label", name="p1"))
    ) and not knownkit.refused(
        lambda: knownkit.act(given, knownkit.made(given), "label", name="p1")
    )


@case(
    "S23",
    "review binds the body digest; act gate",
    "merge of a PR whose Plan was edited after the approval",
)
def _edited(given: knownkit.Kit) -> bool:
    hub = knownkit.made(
        given, knownkit.change(pull={"body": knownkit.BODY + "\nedited"})
    )
    return bool(
        knownkit.refused(lambda: knownkit.act(given, hub, "merge"))
    ) and not hub.act.hub.pull(knownkit.REPO, knownkit.NUMBER).get("merged")


@case("S24", "hold record + act gate", "workflow runs dispatched during the hold")
def _dispatch_held(given: knownkit.Kit) -> bool:
    hub = knownkit.made(given)
    knownkit.act(given, hub, "hold", number="0", scope="ci", source="m1")
    held = knownkit.refused(
        lambda: knownkit.act(
            given, hub, "dispatch-workflow", number="0", workflow="check.yml", ref="b"
        )
    )
    return bool(held) and not knownkit.refused(
        lambda: knownkit.act(
            given,
            knownkit.made(given),
            "dispatch-workflow",
            number="0",
            workflow="check.yml",
            ref="b",
        )
    )
