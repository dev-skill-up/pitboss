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
ISSUES = "repos/owner/project/issues"
NOT_FINISHED = "its branch is not merged or closed, and its name is no closed ticket's"


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


def start(clone: pathlib.Path, path: pathlib.Path, branch: str) -> pathlib.Path:
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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Scene:
    """A world with an empty directory ``deeper`` in its workspace.

    Attributes:
        here: the world.
        deeper: the directory.
    """

    here: world.World
    deeper: pathlib.Path


def scene_of() -> Scene:
    """Make a world with an empty directory ``deeper`` in its workspace.

    Returns:
        The scene.
    """
    here = world.make_world()
    (here.workspace / "deeper").mkdir()
    return Scene(here=here, deeper=here.workspace / "deeper")


def add(scene: Scene, name: str) -> pathlib.Path:
    """Add a worktree of the configured repository in ``deeper``.

    Args:
        scene: the scene.
        name: the directory's and the branch's name.

    Returns:
        The worktree.
    """
    return start(scene.here.clone, scene.deeper / name, name)


def ticket(scene: Scene, number: int, state: str) -> None:
    """Say whether a ticket of the configured repository is open or closed.

    Args:
        scene: the scene.
        number: the ticket's number.
        state: ``open`` or ``closed``.
    """
    scene.here.bodies[f"{ISSUES}/{number}"] = {"state": state}


def pulls(
    scene: Scene, merged: Sequence[str], opened: Sequence[str] = (), slug: str = ""
) -> None:
    """Say which branches have a merged PR and which an open one.

    Args:
        scene: the scene.
        merged: the branches whose PR merged.
        opened: the branches whose PR is open.
        slug: the repository, or empty for the configured one.
    """
    page = fakes.page(f"repos/{slug}/pulls?state=all")
    if not slug:
        page = world.project_page("pulls?state=all")
    states = [(name, MERGED) for name in merged] + [(name, OPEN) for name in opened]
    scene.here.bodies[page] = [{"head": {"ref": ref}, **it} for ref, it in states]


def clean(scene: Scene, *arguments: str, directory: pathlib.Path | None = None) -> str:
    """Run ``clean-container`` with no marker file.

    Args:
        scene: the scene.
        *arguments: more arguments.
        directory: where it runs; the workspace when None.

    Returns:
        What it printed.
    """
    argv = ("clean-container", *cleanworld.NO_MARKER, *arguments)
    return world.again(scene.here, *argv, directory=directory).out


def inside(scene: Scene, *arguments: str) -> str:
    """Run ``clean-container`` in the main clone, with no marker file.

    Args:
        scene: the scene.
        *arguments: more arguments.

    Returns:
        What it printed.
    """
    return clean(scene, *arguments, directory=scene.here.clone)


def blind(scene: Scene) -> Scene:
    """The scene where git cannot list the worktrees of a repository.

    Args:
        scene: the scene.

    Returns:
        The scene.
    """
    processes = NoWorktreeList(inner=scene.here.processes)
    return dataclasses.replace(
        scene, here=dataclasses.replace(scene.here, processes=processes)
    )


class TestFinishedWorktrees(unittest.TestCase):
    """Worktrees one directory below the workspace, and what is said of them."""

    def test_the_dry_run_lists_it_and_the_real_run_removes_it(self) -> None:
        """Run from the main clone: listed, kept in a dry run, gone and FREED after."""
        scene = scene_of()
        merged = add(scene, "pb-316")
        pulls(scene, ["pb-316"])
        dry = inside(scene)
        same((f"REMOVED PATH {merged} " in dry, "FREED" in dry), (True, False))
        same(("(its PR merged) (dry run" in dry, merged.exists()), (True, True))
        real = inside(scene, "--no-dry-run")
        same((f"REMOVED PATH {merged} " in real, " FREED" in real), (True, True))
        listed = fakes.run_git(scene.here.clone, "worktree", "list")
        same((merged.exists(), "pb-316" in listed), (False, False))

    def test_a_worktree_of_another_repository_is_found_too(self) -> None:
        """The clone is of a repository the configuration does not name."""
        scene = scene_of()
        foreign = test_clean_clones.foreign_clone(scene.here, "foreign", "foreign")
        merged = start(foreign, scene.deeper / "other-wt", "other-wt")
        pulls(scene, ["other-wt"], slug=test_clean_clones.FOREIGN)
        test_local.age(foreign)
        out = inside(scene, "--no-dry-run")
        same((f"REMOVED PATH {merged} " in out, merged.exists()), (True, False))
        same(foreign.exists(), True)

    def test_a_worktree_below_a_directory_that_is_not_a_root_is_removed(self) -> None:
        """Its parent is not the workspace, a scratch directory or the root of files."""
        scene = scene_of()
        (scene.deeper / "a/b").mkdir(parents=True)
        merged = start(scene.here.clone, scene.deeper / "a/b/pb-324", "pb-324")
        pulls(scene, ["pb-324"])
        out = clean(scene, "--no-dry-run")
        same((f"REMOVED PATH {merged} " in out, merged.exists()), (True, False))
        same("COULD NOT REMOVE PATH" in out, False)

    def test_when_git_cannot_list_worktrees_only_the_top_is_judged(self) -> None:
        """The deeper worktree is not found and nothing fails."""
        scene = scene_of()
        merged = add(scene, "pb-316")
        pulls(scene, ["pb-316"])
        out = clean(blind(scene), "--no-dry-run")
        same((merged.exists(), "pb-316" in out), (True, False))

    def test_each_kept_worktree_says_why(self) -> None:
        """An open PR, a live marker, a branch with no PR and no closed ticket."""
        scene = scene_of()
        for name in ("open-one", "marked", "plain-one", "pb-9999"):
            add(scene, name)
        pulls(scene, ["marked"], ["open-one"])
        cleanworld.mark_live(scene.deeper / "marked")
        ticket(scene, 9999, "open")
        out = clean(scene)
        top = f"clean: kept {scene.deeper}"
        said = [
            f"{top}/open-one (its branch has an open PR)",
            f"{top}/marked (holds a file named .pitboss-live)",
            f"{top}/plain-one ({NOT_FINISHED})",
            f"{top}/pb-9999 ({NOT_FINISHED})",
        ]
        same(cleanworld.absent(out, said), [])
        same(("REMOVED PATH" in out, "(not a git checkout)" in out), (False, False))

    def test_the_worktree_and_the_scratch_named_for_a_closed_ticket_go(self) -> None:
        """q1079c, a1079 and s-1079.zip are FREED; the others stay."""
        scene = scene_of()
        deeper = scene.deeper
        for name in ("q1079c", "q2000c", "q3000c"):
            add(scene, name)
        ticket(scene, 1079, "closed")
        ticket(scene, 2000, "open")
        for name in ("a1079/notes", "s-1079.zip", "a2079/notes", "b1080"):
            fakes.write(deeper / name, "x")
        test_local.age(deeper)
        out = inside(scene, "--no-dry-run")
        gone = [deeper / name for name in ("q1079c", "a1079", "s-1079.zip")]
        left = ("q2000c", "q3000c", "a2079", "b1080")
        stayed = [(deeper / name).exists() for name in left]
        said = [f"REMOVED PATH {each} " for each in gone]
        same(cleanworld.absent(out, said), [])
        same(out.count(" FREED"), 3)
        same(([each.exists() for each in gone], stayed), ([False] * 3, [True] * 4))
        reasons = ["a ticket named in its name is closed", "named for ticket 1079"]
        same(cleanworld.absent(out, reasons), [])

    def test_scratch_named_for_a_closed_ticket_that_changed_lately_is_kept(
        self,
    ) -> None:
        """The one safety test holds it: it is in use."""
        scene = scene_of()
        add(scene, "q1079c")
        ticket(scene, 1079, "closed")
        fakes.write(scene.deeper / "s-1079.zip", "x")
        out = clean(scene, "--no-dry-run")
        kept = (scene.deeper / "s-1079.zip").exists()
        same((kept, "s-1079.zip" in out), (True, False))


class TestTicketNumbers(unittest.TestCase):
    """The numbers a name holds, and whether a ticket is closed."""

    def test_numbers_are_runs_of_two_to_seven_digits(self) -> None:
        """A single digit, a longer run and a run inside a longer one are not."""
        names = ["pb-316", "q1079c", "a1", "x12345678", "5-77-5"]
        same(ticketclosed.numbers_in(names), [316, 1079, 77])

    def test_the_first_closed_ticket_is_the_one(self) -> None:
        """An open one and one that cannot be read are passed over."""
        bodies = {
            "repos/o/r/issues/11": {"state": "open"},
            "repos/o/r/issues/33": {"state": "closed"},
        }
        github = fakes.github(bodies)
        same(ticketclosed.closed_ticket(github, "o/r", ["x11-22-33-44"]), 33)
        same(ticketclosed.closed_ticket(github, "o/r", ["x11"]), 0)

    def test_the_directories_that_hold_checkouts_are_places(self) -> None:
        """Only those under the workspace are, with the numbers in the names."""
        top = pathlib.Path("/work")
        paths = [top / "w/pb-316", top / "q1079c", pathlib.Path("/else/pb-9999")]
        places, tickets = ticketclosed.where(top, paths)
        same((sorted(places), tickets), ([top, top / "w"], [316, 1079, 9999]))
