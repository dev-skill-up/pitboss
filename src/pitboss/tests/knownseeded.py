"""The 37 seeded faults of the 38 (X36 is no fault: a Plan command is run as written).

Each is a world run through its control, as in ``knowncases``, and registered in
the same ``CASES``.
"""

import re
from typing import Callable

from .. import enumeration
from ..actcore import Owner, Target
from ..totalroutes import instructions
from . import fakehub
from .knowncases import ARMED, _item, case, dispatch, pushed, record
from .knownkit import (
    BASE,
    BODY,
    HEAD,
    NUMBER,
    REPO,
    Kit,
    act,
    brief,
    change,
    draft,
    git,
    goes,
    made,
    refused,
    repo_pair,
    review_with,
    stops,
    verdict,
)
from .totalworld import review

TICKET = "## Done when\n\n- x demonstrated by y\n\nPaths: src/\n"


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
        _item(f"rp#{n}", f"2026-11-0{n}", red_check="canonical-files", red_step="Audit")
        for n in (1, 2, 3)
    ]
    filed = [
        _item(
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
    items = [_item("rp#3", "2026-11-01", red_check="tools-test", red_step="Test")]
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
        items=[_item("q#3", "2026-11-01", step="plan-check-fix", worker="agent-a")]
    )
    hub = made(given)
    return (
        bool(refused(lambda: dispatch(given, hub, state, agent="agent-b")))
        and dispatch(given, hub, state, agent="agent-a") == "q#3"
    )


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
        and hub.hub.pull(REPO, NUMBER)["auto_merge"] is None
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


def dispatch_target() -> Target:
    """The project's repository as a target.

    Returns:
        The target.
    """
    return Target(repo=REPO)


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
