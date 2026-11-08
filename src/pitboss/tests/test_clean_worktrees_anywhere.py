"""``clean-container`` frees the worktrees of finished tickets wherever they are.

The cause of pitboss#348, reproduced here with real git: it looked only at the
directories directly under the workspace, so a worktree one directory further
down (``w/pb-316``), of the configured repository or of another, was never
seen, and a worktree whose branch has no PR but whose ticket is closed
(``q1079c``) was kept as not merged. It must list them, remove them with
``--no-dry-run``, say ``FREED`` for each and say why it keeps one that it keeps.
"""

import dataclasses
import pathlib
import subprocess
import unittest
from typing import Sequence

from .. import ticketclosed
from . import cleanworld, fakes, test_clean_clones, test_local, world

same = cleanworld.same
MERGED = {"state": "closed", "merged_at": "x"}
OPEN = {"state": "open"}
CLOSED_TICKET = {"state": "closed"}
OPEN_TICKET = {"state": "open"}
NO_MARKER = cleanworld.NO_MARKER


def deeper_world() -> tuple[world.World, pathlib.Path]:
    """A world with an empty directory ``deeper`` in its workspace.

    Returns:
        The world and the directory.
    """
    here = world.make_world()
    deeper = here.workspace / "deeper"
    deeper.mkdir()
    return here, deeper


def worktree(clone: pathlib.Path, path: pathlib.Path, branch: str) -> pathlib.Path:
    """Add a worktree on a new branch with a commit, pushed, 10 hours old.

    Args:
        clone: the clone of the repository.
        path: where the worktree goes.
        branch: its branch.

    Returns:
        The worktree.
    """
    fakes.run_git(clone, "worktree", "add", "-q", str(path), "-b", branch)
    fakes.commit_file(path, branch)
    fakes.push(path)
    test_local.age(path)
    return path


def run(
    here: world.World, *arguments: str, directory: pathlib.Path | None = None
) -> world.Result:
    """Run ``clean-container`` in a directory, with no marker file.

    Args:
        here: the world.
        *arguments: more arguments.
        directory: where it runs; the workspace when None.

    Returns:
        What it did.
    """
    return world.again(
        here, "clean-container", *NO_MARKER, *arguments, directory=directory
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NoWorktreeList:
    """Runs commands, but git cannot list the worktrees of a repository.

    Attributes:
        inner: what runs the commands.
    """

    inner: fakes.Processes

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> fakes.Output:
        """Run a command.

        Args:
            cmdargs: the command line.
            **kwargs: what gather passes to ``subprocess.run``.

        Returns:
            The finished process.

        Raises:
            subprocess.CalledProcessError: for ``git worktree list``.
        """
        if cmdargs[3:5] == ["worktree", "list"]:
            raise subprocess.CalledProcessError(128, cmdargs)
        return self.inner(cmdargs, **kwargs)


def project_pulls(here: world.World, *pulls: tuple[str, object]) -> None:
    """Say what GitHub knows of the pull requests of the configured repository.

    Args:
        here: the world.
        *pulls: each head branch and its state.
    """
    page = world.project_page("pulls?state=all")
    here.bodies[page] = [{"head": {"ref": ref}, **state} for ref, state in pulls]


class TestWorktreeOfAMergedBranch(unittest.TestCase):
    """A worktree of a merged branch, beside neither the clone nor the workspace's top."""

    def test_the_dry_run_lists_it_and_the_real_run_removes_it(self) -> None:
        """Run from the main clone: listed, kept in a dry run, gone and FREED after."""
        here, deeper = deeper_world()
        merged = worktree(here.clone, deeper / "pb-316", "pb-316")
        project_pulls(here, ("pb-316", MERGED))
        dry = run(here, directory=here.clone).out
        listed = f"REMOVED PATH {merged} "
        same((listed in dry, "FREED" in dry, merged.exists()), (True, False, True))
        same("(its PR merged) (dry run" in dry, True)
        real = run(here, "--no-dry-run", directory=here.clone).out
        same(
            (f"{listed}" in real, "FREED" in real, merged.exists()), (True, True, False)
        )
        same("pb-316" in fakes.run_git(here.clone, "worktree", "list"), False)

    def test_a_worktree_of_another_repository_is_found_too(self) -> None:
        """The clone is of a repository the configuration does not name."""
        here, deeper = deeper_world()
        foreign = test_clean_clones.foreign_clone(here, "foreign", "foreign")
        merged = worktree(foreign, deeper / "other-wt", "other-wt")
        page = fakes.page(f"repos/{test_clean_clones.FOREIGN}/pulls?state=all")
        here.bodies[page] = [{"head": {"ref": "other-wt"}, **MERGED}]
        test_local.age(foreign)
        out = run(here, "--no-dry-run", directory=here.clone).out
        same((f"REMOVED PATH {merged} " in out, merged.exists()), (True, False))
        same(foreign.exists(), True)

    def test_a_worktree_below_a_directory_that_is_not_a_root_is_removed(self) -> None:
        """Its parent is not the workspace, a scratch directory or the root of files."""
        here, deeper = deeper_world()
        down = deeper / "a" / "b"
        down.mkdir(parents=True)
        merged = worktree(here.clone, down / "pb-324", "pb-324")
        project_pulls(here, ("pb-324", MERGED))
        out = run(here, "--no-dry-run").out
        same((f"REMOVED PATH {merged} " in out, merged.exists()), (True, False))
        same("COULD NOT REMOVE PATH" in out, False)


class TestWorktreesGitCannotList(unittest.TestCase):
    """When git cannot list the worktrees, the directories of the workspace are judged."""

    def test_the_deeper_worktree_is_not_found_and_nothing_fails(self) -> None:
        """Only what is directly under the workspace is looked at."""
        here, deeper = deeper_world()
        merged = worktree(here.clone, deeper / "pb-316", "pb-316")
        project_pulls(here, ("pb-316", MERGED))
        blind = dataclasses.replace(
            here, processes=NoWorktreeList(inner=here.processes)
        )
        out = run(blind, "--no-dry-run").out
        same((merged.exists(), "pb-316" in out), (True, False))


class TestKeptWorktrees(unittest.TestCase):
    """The output says why a worktree of the workspace is kept."""

    def test_each_kept_worktree_says_why(self) -> None:
        """An open PR, a live marker, a branch with no PR and no closed ticket."""
        here, deeper = deeper_world()
        for name in ("open-one", "marked", "plain-one", "pb-9999"):
            worktree(here.clone, deeper / name, name)
        project_pulls(here, ("open-one", OPEN), ("marked", MERGED))
        cleanworld.mark_live(deeper / "marked")
        here.bodies["repos/owner/project/issues/9999"] = OPEN_TICKET
        out = run(here).out
        said = [
            f"clean: kept {deeper}/open-one (its branch has an open PR)",
            f"clean: kept {deeper}/marked (holds a file named .pitboss-live)",
            f"clean: kept {deeper}/plain-one (its branch is not merged or closed,"
            " and its name is no closed ticket's)",
            f"clean: kept {deeper}/pb-9999 (its branch is not merged or closed,"
            " and its name is no closed ticket's)",
        ]
        same(cleanworld.absent(out, said), [])
        same("REMOVED PATH" in out, False)

    def test_a_directory_that_is_no_checkout_is_not_named(self) -> None:
        """Only checkouts are explained."""
        here, deeper = deeper_world()
        out = run(here).out
        same("(not a git checkout)" in out, False)


class TestClosedTicket(unittest.TestCase):
    """A worktree with no PR whose ticket is closed, and what is named for it."""

    def test_the_worktree_and_the_scratch_named_for_the_ticket_go(self) -> None:
        """q1079c, a1079 and s-1079.zip are FREED; the others stay."""
        here, deeper = deeper_world()
        closed = worktree(here.clone, deeper / "q1079c", "q1079c")
        for name in ("q2000c", "q3000c"):
            worktree(here.clone, deeper / name, name)
        here.bodies["repos/owner/project/issues/1079"] = CLOSED_TICKET
        here.bodies["repos/owner/project/issues/2000"] = OPEN_TICKET
        fakes.write(deeper / "a1079" / "notes", "x")
        fakes.write(deeper / "s-1079.zip", "x")
        fakes.write(deeper / "a2079" / "notes", "x")
        fakes.write(deeper / "b1080", "x")
        test_local.age(deeper)
        out = run(here, "--no-dry-run", directory=here.clone).out
        gone = [deeper / "q1079c", deeper / "a1079", deeper / "s-1079.zip"]
        left = [deeper / name for name in ("q2000c", "q3000c", "a2079", "b1080")]
        said = [f"REMOVED PATH {each} " for each in gone]
        same(cleanworld.absent(out, said), [])
        same(out.count(" FREED"), 3)
        same([each.exists() for each in [*gone, *left]], [False] * 3 + [True] * 4)
        same(closed.exists(), False)
        shows = ["a ticket named in its name is closed", "named for ticket 1079"]
        same(cleanworld.absent(out, shows), [])

    def test_a_scratch_entry_changed_lately_is_kept(self) -> None:
        """The one safety test holds it: it is in use."""
        here, deeper = deeper_world()
        worktree(here.clone, deeper / "q1079c", "q1079c")
        here.bodies["repos/owner/project/issues/1079"] = CLOSED_TICKET
        fakes.write(deeper / "s-1079.zip", "x")
        out = run(here, "--no-dry-run").out
        same((deeper / "s-1079.zip").exists(), True)
        same("s-1079.zip" in out, False)


class TestTicketNumbers(unittest.TestCase):
    """The numbers a name holds, and whether a ticket is closed."""

    def test_numbers_are_runs_of_two_to_seven_digits(self) -> None:
        """A single digit, a longer run and a run inside a longer one are not."""
        found = ticketclosed.numbers_in(
            ["pb-316", "q1079c", "a1", "x12345678", "5-77-5"]
        )
        same(found, [316, 1079, 77])

    def test_the_first_closed_ticket_is_the_one(self) -> None:
        """An open one and one that cannot be read are passed over."""
        bodies = {
            "repos/o/r/issues/11": {"state": "open"},
            "repos/o/r/issues/33": {"state": "closed"},
        }
        github = fakes.github(bodies)
        names: Sequence[str] = ["x11-22-33-44"]
        same(ticketclosed.closed_ticket(github, "o/r", names), 33)
        same(ticketclosed.closed_ticket(github, "o/r", ["x11"]), 0)
