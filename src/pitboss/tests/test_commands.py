"""End-to-end tests of the commands: a fake GitHub, real git."""

import contextlib
import dataclasses
import io
import pathlib
import tempfile
import unittest
from typing import Sequence

from gather import commands as gather_commands
from hamcrest import (
    assert_that,
    contains_string,
    equal_to,
    has_item,
    is_not,
    starts_with,
)

from .. import ENTRY_DATA
from . import fakes

FUTURE = "2030-01-01T00:00:00+00:00"
EXTRA = """
[libraries]
repositories = ["lib", "gone"]
no_auto_merge = ["lib"]

[review]
gated = ["gated"]

[slots]
ledger = "{ledger}"
models = ["small", "large"]
priority_labels = ["urgent"]
default = [{{name = "tiny", model = "small"}}, {{name = "big", model = "large"}}]
"""
GREEN = {"id": 7, "name": "build", "status": "completed", "conclusion": "success"}
RED = {"id": 8, "name": "test", "status": "completed", "conclusion": "failure"}
APPROVAL = {
    "state": "APPROVED",
    "commit_id": fakes.SHA_A,
    "author_association": "MEMBER",
    "submitted_at": "2026-10-02T00:00:00Z",
}
COMMENT = {
    "body": f"## Review\nReviewed: {fakes.SHA_A}\nVerdict: approved\n",
    "author_association": "MEMBER",
    "created_at": "2026-10-02T00:00:00Z",
}


def _pull(slug: str, number: int, *, checks: object, **changes: object) -> dict[str, object]:
    reviewed = number == 2 or slug.endswith("lib")
    head = fakes.SHA_A if reviewed else str(number) * 40
    reviews = [APPROVAL] if number == 2 else []
    comments = [COMMENT] if slug.endswith("lib") else []
    branch = {"sha": head, "ref": f"branch-{number}"}
    return {
        f"repos/{slug}/pulls/{number}": fakes.pull_body(number, head=branch, **changes),
        fakes.page(f"repos/{slug}/issues/{number}/comments"): comments,
        fakes.page(f"repos/{slug}/pulls/{number}/reviews"): reviews,
        fakes.page(f"repos/{slug}/commits/{head}/check-runs"): {
            "check_runs": checks
        },
        fakes.page(f"repos/{slug}/pulls/{number}/files"): [{"filename": "f"}],
    }


def _run(identifier: int, number: int, group: str, status: str) -> dict[str, object]:
    return {
        "id": identifier,
        "status": status,
        "conclusion": None,
        "created_at": f"2029-12-31T23:{identifier:02d}:00+00:00",
        "head_branch": f"gh-readonly-queue/main/pr-{number}-{group}",
    }


def bodies() -> dict[str, object]:
    """The fake GitHub of the tests.

    Returns:
        The canned bodies.
    """
    project = "repos/owner/project"
    found: dict[str, object] = {
        project: {},
        "repos/owner/lib": {},
        fakes.page(f"{project}/pulls?state=open"): [
            {"number": 1},
            {"number": 2},
            {"number": 3},
        ],
        fakes.page("repos/owner/lib/pulls?state=open"): [{"number": 4}],
        fakes.page(f"{project}/actions/runs?event=merge_group"): {
            "workflow_runs": [
                _run(11, 2, "old", "queued"),
                _run(12, 2, "new", "in_progress"),
            ]
        },
        fakes.page("repos/owner/lib/actions/runs?event=merge_group"): {
            "workflow_runs": []
        },
        fakes.page(f"{project}/actions/runs/11/jobs"): {"jobs": [{"status": "queued"}]},
        fakes.page(f"{project}/actions/runs/12/jobs"): {"jobs": []},
        f"POST {project}/actions/runs/11/cancel": {},
        fakes.page(f"{project}/pulls?state=all"): [
            {"head": {"ref": "merged-work"}, "state": "closed", "merged_at": "x"}
        ],
        fakes.page(f"{project}/issues?state=open&labels=urgent"): [
            {
                "number": 9,
                "title": "A ticket",
                "created_at": "2026-09-01T00:00:00+00:00",
                "labels": [{"name": "urgent"}],
            }
        ],
        fakes.page("repos/owner/lib/issues?state=open&labels=urgent"): [],
    }
    found.update(_pull("owner/project", 1, checks=[RED], mergeable_state="dirty"))
    found.update(_pull("owner/project", 2, checks=[GREEN]))
    found.update(_pull("owner/project", 3, checks=[GREEN]))
    found.update(_pull("owner/lib", 4, checks=[GREEN]))
    return found


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class World:
    """A workspace with a clone, a finished worktree, a config and a fake GitHub.

    Attributes:
        workspace: the workspace.
        clone: the main clone.
        worktree: a worktree whose PR merged.
        ledger: the slot ledger.
        config: the configuration file.
        fake: the fake processes.
    """

    workspace: pathlib.Path
    clone: pathlib.Path
    worktree: pathlib.Path
    ledger: pathlib.Path
    config: str
    fake: fakes.FakeProcesses


def make_world() -> World:
    """Make a world.

    Returns:
        The world.
    """
    workspace = pathlib.Path(tempfile.mkdtemp())
    _, clone = fakes.make_repository(workspace)
    worktree = workspace / "merged-work"
    fakes.run_git(clone, "worktree", "add", "-q", str(worktree), "-b", "merged-work")
    fakes.run_git(worktree, "push", "-q", "origin", "merged-work")
    ledger = workspace / "ledger.json"
    fakes.settings(workspace, EXTRA.format(ledger=ledger))
    return World(
        workspace=workspace,
        clone=clone,
        worktree=worktree,
        ledger=ledger,
        config=str(workspace / "project.toml"),
        fake=fakes.FakeProcesses(bodies=bodies()),
    )


def invoke(world: World, *argv: str) -> tuple[str, str, object]:
    """Run ``pitboss`` with arguments.

    Args:
        world: the world.
        *argv: the arguments.

    Returns:
        Its standard output, standard error and exit code.
    """
    out, err = io.StringIO(), io.StringIO()
    code: object = 0
    parser = gather_commands.set_parser(collected=ENTRY_DATA.collector.collect())
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            gather_commands.run_maybe_dry(
                parser=parser,
                argv=["pitboss", *argv],
                env={"PWD": str(world.workspace)},
                sp_run=world.fake,
            )
        except SystemExit as exit_error:
            code = exit_error.code
    return out.getvalue(), err.getvalue(), code


def lines(world: World, *argv: str) -> Sequence[str]:
    """Run ``pitboss`` and split its output.

    Args:
        world: the world.
        *argv: the arguments.

    Returns:
        The lines of standard output.
    """
    return invoke(world, *argv)[0].splitlines()


class Commands(unittest.TestCase):
    """Running the commands."""

    def setUp(self) -> None:
        """Make a world."""
        self.world = make_world()

    def test_sweep(self) -> None:
        """The sweep reports every section and exits 1 on a red or conflicted PR."""
        (self.world.clone / "scratch").write_text("unsaved")
        broken = self.world.workspace / "broken"
        fakes.run_git(self.world.workspace, "init", "-q", str(broken))
        fakes.run_git(broken, "remote", "add", "origin", "/nowhere")
        out, err, code = invoke(self.world, "sweep", self.world.config, "--now", FUTURE)
        assert_that(code, equal_to(1))
        for text in [
            "UNREADABLE owner/gone: gh: not found",
            "owner/project#1 [dirty] auto-merge=off pending=0 failed=[test (job 8)]",
            "CONFLICT owner/project#1: merge main into branch-1",
            "FAILED owner/project#1: test: read gh api repos/owner/project/actions/jobs/8",
            "READY TO MERGE owner/project#2",
            "AUTO MERGE OFF owner/project#3",
            "queue=in_progress",
            "MERGE BY HAND owner/lib#4",
            "RUNNER PRESSURE: 1 queue-run jobs",
            "STALE QUEUE RUN owner/project 11 (pr-2, queued)",
            "QUEUE RUN owner/project 12 (pr-2, in_progress, 48 of 60 minutes)",
            f"STALE WORKTREE {self.world.worktree} [merged-work] (its PR merged)",
            "SWEEP REMINDER: Is any ticket closeable?",
            f"fetch failed in {broken}",
            f"STRAGGLER {self.world.clone} [main] uncommitted=1",
            "EMPTY SLOT: tiny (small)",
        ]:
            assert_that(out, contains_string(text))
        assert_that(err, contains_string("CHECK BEFORE YOU ANSWER"))
        assert_that(err, contains_string("] checkouts done"))

    def test_sweep_healthy(self) -> None:
        """With no red or conflicted PR the sweep exits 0."""
        listing = fakes.page("repos/owner/project/pulls?state=open")
        self.world.fake.bodies[listing] = [{"number": 2}]
        _, _, code = invoke(self.world, "sweep", self.world.config, "--now", FUTURE)
        assert_that(code, equal_to(0))

    def test_pressure(self) -> None:
        """The pressure command prints one line and exits 1 under pressure."""
        out, _, code = invoke(self.world, "pressure", self.world.config)
        assert_that(out, starts_with("UNREADABLE owner/gone"))
        assert_that(out.splitlines()[-1], starts_with("RUNNER PRESSURE: 1"))
        assert_that(code, equal_to(1))

    def test_no_pressure(self) -> None:
        """Without a waiting job there is no pressure."""
        jobs = fakes.page("repos/owner/project/actions/runs/11/jobs")
        self.world.fake.bodies[jobs] = {"jobs": []}
        out, _, code = invoke(self.world, "pressure", self.world.config)
        assert_that(out, contains_string("NO RUNNER PRESSURE: push and merge"))
        assert_that(code, equal_to(0))

    def test_cancel_stale_runs(self) -> None:
        """Stale runs are cancelled only with --no-dry-run."""
        dry = lines(self.world, "cancel-stale-runs", self.world.config)
        assert_that(dry, has_item(contains_string("11 (dry run")))
        posts = [call for call in self.world.fake.calls if "POST" in call]
        assert_that(posts, equal_to([]))
        real = lines(self.world, "cancel-stale-runs", self.world.config, "--no-dry-run")
        assert_that(real, has_item("CANCELLED STALE QUEUE RUN owner/project 11"))

    def test_cancel_refused(self) -> None:
        """A cancel GitHub refuses is reported."""
        del self.world.fake.bodies["POST repos/owner/project/actions/runs/11/cancel"]
        found = lines(self.world, "cancel-stale-runs", self.world.config, "--no-dry-run")
        assert_that(found, has_item("COULD NOT CANCEL STALE QUEUE RUN owner/project 11"))

    def test_clean_worktrees(self) -> None:
        """Stale worktrees are removed only with --no-dry-run."""
        dry = lines(self.world, "clean-worktrees", self.world.config, "--now", FUTURE)
        assert_that(dry, has_item(contains_string("(dry run")))
        assert_that(self.world.worktree.exists(), equal_to(True))
        real = lines(self.world, "clean-worktrees", self.world.config, "--now", FUTURE, "--no-dry-run")
        assert_that(real, has_item(starts_with(f"REMOVED WORKTREE {self.world.worktree}")))
        assert_that(self.world.worktree.exists(), equal_to(False))

    def test_clean_worktree_refused(self) -> None:
        """A worktree git will not remove is reported."""
        fakes.run_git(self.world.clone, "worktree", "lock", str(self.world.worktree))
        found = lines(self.world, "clean-worktrees", self.world.config, "--now", FUTURE, "--no-dry-run")
        assert_that(found, has_item(f"COULD NOT REMOVE WORKTREE {self.world.worktree}"))

    def test_review_form(self) -> None:
        """The form is printed, with the gated rules for a gated repository."""
        gated = lines(self.world, "review-form", self.world.config, "gated")
        assert_that(gated[0], equal_to("# owner/gated: gated"))
        assert_that(gated, has_item("Reviewed: {sha}"))
        plain = lines(self.world, "review-form", self.world.config, "other/lib")
        assert_that(plain[0], equal_to("# other/lib: not gated"))
        assert_that(plain, is_not(has_item(contains_string("ASCII only"))))

    def test_unreadable_project(self) -> None:
        """A project the session cannot read stops the command."""
        del self.world.fake.bodies["repos/owner/project"]
        _, _, code = invoke(self.world, "pressure", self.world.config)
        assert_that(code, equal_to("cannot read owner/project"))


class SlotCommands(unittest.TestCase):
    """Running ``slots``."""

    def setUp(self) -> None:
        """Make a world."""
        self.world = make_world()

    def test_ledger(self) -> None:
        """Slots are taken, freed, added, removed, and checked."""
        found = lines(self.world, "slots", "set", self.world.config, "tiny", "agent-1", "#9")
        assert_that(found, has_item("slot tiny (small): owner/project#9 (agent-1)"))
        lines(self.world, "slots", "add", self.world.config, "spare", "large")
        lines(self.world, "slots", "remove", self.world.config, "big")
        found = lines(self.world, "slots", "show", self.world.config)
        assert_that(found, has_item(contains_string("EMPTY SLOT: spare (large)")))
        lines(self.world, "slots", "set", self.world.config, "spare", "agent-2", "lib#1")
        found = lines(self.world, "slots", "check", self.world.config, "--running", "agent-2")
        assert_that(found, has_item(starts_with("GONE AGENT: slot tiny holds agent-1")))
        assert_that(found, has_item("slots: the ledger says all full"))
        lines(self.world, "slots", "free", self.world.config, "tiny")
        lines(self.world, "slots", "failed", self.world.config, "#9", "small")
        assert_that(self.world.ledger.read_text(), contains_string('"owner/project#9"'))

    def test_refusals(self) -> None:
        """A wrong word count or a refused change exits 2."""
        _, err, code = invoke(self.world, "slots", "set", self.world.config, "tiny")
        assert_that((code, err), equal_to((2, "slots set takes 3 words\n")))
        invoke(self.world, "slots", "set", self.world.config, "tiny", "agent-1", "#9")
        _, err, code = invoke(self.world, "slots", "set", self.world.config, "tiny", "agent-2", "#9")
        assert_that(code, equal_to(2))
        assert_that(err, contains_string("refused: slot tiny holds agent-1"))

    def test_next(self) -> None:
        """The list is sorted, and each empty slot takes what it may."""
        invoke(self.world, "slots", "failed", self.world.config, "#3", "small")
        found = lines(self.world, "slots", "next", self.world.config, "--now", FUTURE)
        assert_that(
            [line.split(" (")[0] for line in found if line.startswith("NEXT")],
            equal_to(
                [
                    "NEXT 1. owner/project#3",
                    "NEXT 2. owner/project#9",
                ]
            ),
        )
        assert_that(
            found,
            has_item(starts_with("EMPTY SLOT: tiny (small): start owner/project#9")),
        )
        assert_that(
            found,
            has_item(starts_with("EMPTY SLOT: big (large): start owner/project#3")),
        )

    def test_next_when_full(self) -> None:
        """With every slot full, nothing is started."""
        invoke(self.world, "slots", "set", self.world.config, "tiny", "a", "x")
        invoke(self.world, "slots", "set", self.world.config, "big", "b", "y")
        found = lines(self.world, "slots", "next", self.world.config, "--now", FUTURE)
        assert_that(found, has_item("slots: the ledger says all full: start nothing"))

    def test_next_nothing_fits(self) -> None:
        """A slot nothing fits is left empty."""
        invoke(self.world, "slots", "remove", self.world.config, "big")
        invoke(self.world, "slots", "failed", self.world.config, "#9", "small")
        invoke(self.world, "slots", "failed", self.world.config, "#3", "small")
        found = lines(self.world, "slots", "next", self.world.config, "--now", FUTURE)
        assert_that(found, has_item("EMPTY SLOT: tiny (small): nothing fits it: leave it empty"))
