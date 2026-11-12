"""The known gaps G15 to G29, each a world run through its control.

A case passes only when its control refuses the unsafe world and lets its safe
twin through; ``test_known`` runs every table.
"""

import pathlib

from .. import dispatchnext, handbackform
from . import fakehub, scratch
from .knowngit import git, remote_head, repo_pair
from .knownkit import (
    Known,
    HEAD,
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
    pushed,
    refused,
    registry,
    review_with,
    stops,
    verdict,
)

from .totalworld import ARMED, files_of, item, record

CASES: dict[str, Known] = {}
case = registry(CASES)


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
        item("q#1119", "2026-11-10"),
        dispatchnext.Item(
            ref="q#1200", kind="ticket", priority="p0", created="2026-11-12"
        ),
    ]
    url = "https://github.com/bats-lang/quire/pull/1119"
    partial = (
        f"## Items\n- [1] done | evidence: {url}\n- [2] done, except the e2e spec |"
        f" evidence: {url}\n"
    )
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


@case("G18", "hold disarms; act gate", "auto-merge re-armed during a hold")
def _rearmed(given: Kit) -> bool:
    hub = made(given, change(pull=ARMED, events=[record(f"arm head={HEAD}")]))
    act(given, hub, "hold", number="0", scope="merges", source="m1")
    return hub.act.hub.pull(REPO, NUMBER)["auto_merge"] is None and bool(
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
    files = files_of(".github/workflows/relock.yml", 2, 1)
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
    body = (
        "## Done when\n\n- a demonstrated by b\n- c demonstrated by d\n\nFound by"
        " quire#1118.\n"
    )
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


@case(
    "G29",
    "mutants run only in the CI job: no CLI command runs them",
    "a worker ran mutation-check on a host as root and a mutant replaced the null"
    " device",
)
def _mutants(given: Kit) -> bool:
    return bool(given.registrations(_tree(True))) and not given.registrations(
        _tree(False)
    )
