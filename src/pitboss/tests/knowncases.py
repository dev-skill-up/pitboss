"""The 29 known gaps, each a world run through its control (cast-477-final.md, 5.5).

A case is true only when its control refuses the unsafe world and lets the safe
twin through. ``CASES`` holds every case of this module and of ``knownseeded``.
"""

import copy
import dataclasses
import pathlib
from typing import Callable, Mapping

from .. import actcore, dispatchnext, handbackform, rulecases
from . import fakehub, scratch, totalworld
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
    remote_head,
    repo_pair,
    review_with,
    stops,
    verdict,
)

Case = Callable[[Kit], bool]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Known:
    """One case.

    Attributes:
        control: the control that holds it.
        what: the world that was run.
        run: the case.
    """

    control: str
    what: str
    run: Case


CASES: dict[str, Known] = {}


def case(name: str, control: str, what: str) -> Callable[[Case], Case]:
    """Register a case.

    Args:
        name: its id.
        control: the control that holds it.
        what: the world that was run.

    Returns:
        The decorator.
    """

    def register(run: Case) -> Case:
        CASES[name] = Known(control=control, what=what, run=run)
        return run

    return register


def dispatch(
    given: Kit, hub: fakehub.Made, state: dispatchnext.State, **options: str
) -> str:
    """Run ``dispatch-next`` over a state.

    Args:
        given: the kit.
        hub: the hub and the verb's world.
        state: what the order reads.
        **options: ``want`` and ``agent``.

    Returns:
        The item it answers.
    """
    world = dataclasses.replace(hub.act, work=lambda: state)
    return given.verbs["dispatch-next"](world, actcore.Target(repo=REPO), options)


def pushed(
    given: Kit, worktree: pathlib.Path, prepush: tuple[int, str] = (0, "ok\n")
) -> str:
    """Run ``push`` of a worktree to ``worker/7``.

    Args:
        given: the kit.
        worktree: the worktree.
        prepush: what the pre-push check says.

    Returns:
        What it said.
    """
    hub = made(given)
    world = dataclasses.replace(hub.act, prepush=lambda: prepush)
    options = {"worktree": str(worktree), "branch": "worker/7"}
    return given.verbs["push"](world, actcore.Target(repo=REPO), options)


def _item(ref: str, created: str, **fields: str) -> dispatchnext.Item:
    return dispatchnext.Item(ref=ref, kind="pr", created=created, **fields)


def record(words: str) -> object:
    """An act record event.

    Args:
        words: what follows ``pitboss-act:``.

    Returns:
        The event.
    """
    return {
        "event": "commented",
        "user": {"login": totalworld.ACT},
        "body": f"pitboss-act: {words}",
    }


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
        and hub.act.owner.cap == 1
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
        and not hub.hub.pull(REPO, NUMBER).get("merged")
    )


@case("G3", "hold record + act gate", "undraft while undrafts are held")
def _undrafts_held(given: Kit) -> bool:
    free = not refused(lambda: act(given, made(given, draft()), "undraft"))
    hub = made(given, draft())
    act(given, hub, "hold", number="0", scope="undrafts", source="m1")
    return (
        free
        and bool(refused(lambda: act(given, hub, "undraft")))
        and hub.hub.pull(REPO, NUMBER)["draft"] is True
    )


def _files(name: str, added: int, removed: int = 0) -> Mapping[str, object]:
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


@case(
    "G4",
    "verdict diff row + recorded override",
    "a ruling allowed 4 added lines in CLAUDE.md; the gate refused them with no route",
)
def _override(given: Kit) -> bool:
    world = change(ctx=_files("CLAUDE.md", 4))
    lines = [
        each
        for each in verdict(given, "arm", world).lines
        if each.startswith("diff: CLAUDE.md")
    ]
    if not lines:
        return False
    words = f'override head={HEAD} stop="{lines[0]}" reason="ruling repository-prototype#684"'
    return goes(
        given, "arm", change(ctx=_files("CLAUDE.md", 4), events=[record(words)])
    )


@case(
    "G5",
    "verdict diff row (GitHub's own count)",
    "a blank added line counted by one version and not another",
)
def _counted(given: Kit) -> bool:
    return stops(
        given, "merge", change(ctx=_files("CLAUDE.md", 1)), "diff: CLAUDE.md"
    ) and goes(given, "merge", change(ctx=_files("CLAUDE.md", 0, 3)))


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
        "## Plan\n\n| 9 | `python3 /tmp/claude-0/x/scratchpad/canonical_check.py` | exits 0 |\n",
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


def _fixme(action: str, world: Mapping[str, object], everywhere: bool) -> str:
    stop = world["adds_fixme"] and (everywhere or world["repo"] != "bats-lang/quire")
    return "STOP" if stop else "GO"


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
        _item(f"rp#{n}", f"2026-11-0{n}", red_check="canonical-files", red_step="Audit")
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
    timeline = hub.hub.timeline(REPO, NUMBER)
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


@case(
    "G15",
    "brief: every rule file on the ticket's paths",
    "pwa's `We write bats, not shell` in the brief for a pwa ticket",
)
def _pwa_shell(given: Kit) -> bool:
    text, ticket = brief(given, "pwa", "src/lib.bats")
    return "We write bats, not shell" in text and not given.recount(text, ticket)


@case(
    "G16",
    "hand-back form; dispatch order",
    "a partial hand-back, and the unfinished PR passed over for a newer ticket",
)
def _partial(given: Kit) -> bool:
    items = [
        _item("q#1119", "2026-11-10"),
        dispatchnext.Item(
            ref="q#1200", kind="ticket", priority="p0", created="2026-11-12"
        ),
    ]
    url = "https://github.com/bats-lang/quire/pull/1119"
    partial = f"## Items\n- [1] done | evidence: {url}\n- [2] done, except the e2e spec | evidence: {url}\n"
    hub, state = made(given), fakehub.state(items=items)
    order = (
        bool(refused(lambda: dispatch(given, hub, state, want="q#1200")))
        and dispatch(given, hub, state, want="q#1119") == "q#1119"
    )
    return (
        bool(given.findings(partial, ["1", "2"], handbackform.in_checkout(None)))
        and order
    )


@case("G17", "review form (closed)", "an Execution review with no `Execution:` line")
def _no_execution(given: Kit) -> bool:
    return stops(
        given,
        "merge",
        change(
            events=[review_with(lambda text: text.replace("Execution: approved\n", ""))]
        ),
        "review:",
    )


ARMED = {"auto_merge": {"merge_method": "merge"}}


@case("G18", "hold disarms; act gate", "auto-merge re-armed during a hold")
def _rearmed(given: Kit) -> bool:
    hub = made(given, change(pull=ARMED, events=[record(f"arm head={HEAD}")]))
    act(given, hub, "hold", number="0", scope="merges", source="m1")
    return hub.hub.pull(REPO, NUMBER)["auto_merge"] is None and bool(
        refused(lambda: act(given, hub, "arm"))
    )


@case(
    "G19",
    "verdict event row (closed world)",
    "the PR was removed from the merge queue and nothing said so",
)
def _dequeued(given: Kit) -> bool:
    events = [{"event": "added_to_merge_queue"}, {"event": "removed_from_merge_queue"}]
    return stops(
        given, "merge", change(events=events), "event removed_from_merge_queue"
    ) and goes(given, "merge", change(events=events[:1]))


@case(
    "G20",
    "brief carries the verdict's path gates; verdict diff row",
    "relock.yml's scratch-run gate missing from the worker's brief",
)
def _relock_gate(given: Kit) -> bool:
    text, _ = brief(given, "quire", ".github/workflows/relock.yml")
    files = _files(".github/workflows/relock.yml", 2, 1)
    unlinted = stops(
        given, "arm", change(ctx={**files, "statuses": []}), "diff: a workflow file"
    )
    return (
        "GATES ON THESE PATHS" in text
        and "scratch run" in text
        and unlinted
        and goes(given, "arm", change(ctx=files))
    )


@case(
    "G21",
    "verdict status row on undraft",
    "undraft with a failed text-lint status on the head",
)
def _undraft_red(given: Kit) -> bool:
    red = draft({"statuses": [{"context": "text-lint", "state": "failure"}]})
    return stops(given, "undraft", red, "status text-lint") and goes(
        given, "undraft", draft()
    )


@case(
    "G22",
    "act push: assigned branch, read back",
    "a push that went to another branch, reported as pushed",
)
def _other_branch(given: Kit) -> bool:
    worktree = repo_pair()
    head = pushed(given, worktree)
    git(worktree, "checkout", "-q", "-b", "other")
    return head == remote_head(worktree) and bool(
        refused(lambda: pushed(given, worktree))
    )


@case(
    "G23",
    "act push: no empty commit",
    "an empty commit pushed for a revision of the body alone",
)
def _empty(given: Kit) -> bool:
    worktree = repo_pair()
    git(worktree, "commit", "-q", "--allow-empty", "-m", "re-run")
    return "empty commit" in refused(
        lambda: pushed(given, worktree)
    ) and not remote_head(worktree)


@case(
    "G24",
    "review binds the body digest",
    "an approval with no digest outlives the revised Plan",
)
def _no_digest(given: Kit) -> bool:
    bare = review_with(
        lambda text: "\n".join(
            line for line in text.splitlines() if not line.startswith("Body:")
        )
    )
    return stops(
        given,
        "merge",
        change(events=[bare]),
        "review: the newest review has no single `Body:",
    )


@case(
    "G25",
    "act push: the pre-push check must say ok",
    "the pre-push check errored and the push went through",
)
def _prepush(given: Kit) -> bool:
    worktree = repo_pair()
    errored = refused(lambda: pushed(given, worktree, (2, "bats: command not found")))
    silent = refused(lambda: pushed(given, worktree, (0, "warning: skipped")))
    return (
        bool(errored and silent)
        and not remote_head(worktree)
        and bool(pushed(given, worktree))
    )


@case(
    "G26",
    "ticket reader (closed world)",
    "`Found by quire#1118.` read as a Done-when item",
)
def _found_by(given: Kit) -> bool:
    body = "## Done when\n\n- a demonstrated by b\n- c demonstrated by d\n\nFound by quire#1118.\n"
    read = list(given.controls.items(body)) == [
        "a demonstrated by b",
        "c demonstrated by d",
    ]
    return read and bool(
        refused(lambda: given.controls.items(body.replace("Found by", "Also see")))
    )


@case(
    "G27",
    "a failed check is not overridable; rulings as cases",
    "a ruling that waives a red",
)
def _waived(given: Kit) -> bool:
    red = {"statuses": [{"context": "check-e2e", "state": "failure"}]}
    line = [
        each
        for each in verdict(given, "arm", change(ctx=red)).lines
        if each.startswith("status ")
    ][0]
    words = (
        f'override head={HEAD} stop="{line}" reason="Opus ruling: known flake, arm it"'
    )
    world = change(ctx=red, events=[record(words)])
    return stops(given, "arm", world, "status check-e2e") and bool(
        refused(
            lambda: act(
                given, made(given, world), "override", stop=line, reason="known flake"
            )
        )
    )


@case(
    "G28",
    "brief: every rule file on the ticket's paths",
    "no setup step and no check rule in the worker's brief (quire#1065)",
)
def _quire_setup(given: Kit) -> bool:
    text, ticket = brief(given, "quire", "src/app.bats")
    return (
        "Check locally before every push" in text
        and ".github/bats-version" in text
        and not given.recount(text, ticket)
    )


def _tree(registered: bool) -> pathlib.Path:
    root = scratch.directory()
    (root / "src" / "pitboss").mkdir(parents=True)
    words = (
        'COMMAND = Command(\n    name="mutation-check",\n)\n'
        if registered
        else "def run_in_ci(): ...\n"
    )
    (root / "src" / "pitboss" / "mutation_commands.py").write_text(
        words, encoding="utf-8"
    )
    return root


@case(
    "G29",
    "mutants run only in the CI job: no CLI command runs them",
    "a worker ran mutation-check on a host as root and a mutant replaced the null device",
)
def _mutants(given: Kit) -> bool:
    return bool(given.registrations(_tree(True))) and not given.registrations(
        _tree(False)
    )
