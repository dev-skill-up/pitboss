"""``hand-back-check`` reads the checkout a hand-back names (hand-back-done, #471)."""

import contextlib
import os
import pathlib
import subprocess
import unittest
from typing import Iterator, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import handbackcheck
from . import fakes, repositories, world
from .test_deviations import saved

SLUG = "owner/project"
OUTPUT = "Plan check\nrow 1: ran, exit status 0\nPlan check: ok\n"


def made(
    origin: str = f"https://github.com/{SLUG}.git",
) -> tuple[world.World, pathlib.Path, str]:
    """A world with a worktree that holds a commit of its own.

    Args:
        origin: the address of the worktree's ``origin``.

    Returns:
        The world, the worktree and its head.
    """
    here = world.make_world()
    tree = repositories.add_worktree(here.clone, "worker-471")
    repositories.commit_file(tree, "worker-work")
    url = origin
    fakes.run_git(tree, "remote", "set-url", "origin", url)
    return here, tree, fakes.run_git(tree, "rev-parse", "HEAD").split()[0]


def post(here: world.World, head: str, comments: object) -> None:
    """Make the fake GitHub list the PR of a head and its comments.

    Args:
        here: the world.
        head: the head.
        comments: the PR's comments; None for a head with no PR, text that is
            not JSON for a listing that cannot be read.
    """
    listing = f"repos/{SLUG}/commits/{head}/pulls"
    here.bodies[listing] = "not json" if comments == "not json" else [{"number": 5}]
    if comments is None:
        del here.bodies[listing]
    here.bodies[fakes.page(f"repos/{SLUG}/issues/5/comments")] = comments


def record_ok(tree: pathlib.Path, head: str, output: str = OUTPUT) -> None:
    """Record a ``plan-check`` that printed ok.

    Args:
        tree: the worktree.
        head: the head.
        output: its whole output.
    """
    git_dir = pathlib.Path(
        fakes.run_git(tree, "rev-parse", "--absolute-git-dir").strip()
    )
    handbackcheck.record_plan_check(git_dir, head, output)


def run_check(here: world.World, text: str) -> world.Result:
    """Run ``hand-back-check`` on a hand-back.

    Args:
        here: the world.
        text: the hand-back.

    Returns:
        What it did.
    """
    options = [saved(text), "--config", here.config]
    return world.invoke(here, "hand-back-check", *options)


def check(here: world.World, head: str) -> world.Result:
    """Run ``hand-back-check`` on a hand-back that names a head.

    Args:
        here: the world.
        head: the head.

    Returns:
        What it did.
    """
    return run_check(here, f"PR 5\nhead {head}\nDeviations: none\n")


def refused_with(found: world.Result, parts: Sequence[str]) -> None:
    """Assert that a check was refused, with these words.

    Args:
        found: what it did.
        parts: what the refusal says.
    """
    assert_that(
        (found.code, [part in found.out for part in parts]),
        equal_to((1, [True] * len(parts))),
    )


@contextlib.contextmanager
def job_in(tree: pathlib.Path) -> Iterator[int]:
    """A process that works in a directory, ended when the block ends.

    Args:
        tree: its working directory.

    Yields:
        Its process id.
    """
    child = subprocess.Popen(["sleep", "60"], cwd=tree)
    try:
        yield child.pid
    finally:
        child.kill()
        child.wait()


class TestHandBackDone(unittest.TestCase):
    """The checks of the head a hand-back names."""

    def test_a_posted_plan_check_at_the_head_is_accepted_once(self) -> None:
        """The first hand-back is ok; the second for the head is refused."""
        here, tree, head = made()
        record_ok(tree, head)
        post(here, head, [{"body": OUTPUT}])
        first, second = check(here, head), check(here, head)
        assert_that((first.code, first.out), equal_to((0, "ok\n")))
        refused_with(second, ["already accepted", head, "once"])

    def test_a_plan_check_not_run_at_the_head_is_refused(self) -> None:
        """No record, no hand-back."""
        here, _, head = made()
        refused_with(check(here, head), ["has not printed ok", head])

    def test_what_is_not_the_post_is_refused(self) -> None:
        """Another text, no comment, another first line, no origin, no JSON."""
        refused = "Plan check\nPlan check: refused\n"
        other = "Other\nok\n"
        cases = [
            (OUTPUT, [{"body": refused}, {}]),
            (other, [{"body": other}]),
            (OUTPUT, None),
            (OUTPUT, "not json"),
        ]
        for output, comments in cases:
            here, tree, head = made()
            record_ok(tree, head, output)
            post(here, head, comments)
            assert_that(check(here, head).out, contains_string("is not posted"))

    def test_a_worktree_without_a_github_origin_posts_nothing(self) -> None:
        """No slug, nothing is posted."""
        here, tree, head = made("/elsewhere")
        record_ok(tree, head)
        post(here, head, [{"body": OUTPUT}])
        assert_that(check(here, head).out, contains_string("is not posted"))

    def test_a_job_still_running_in_the_worktree_is_refused(self) -> None:
        """The refusal names the job."""
        here, tree, head = made()
        record_ok(tree, head)
        post(here, head, [{"body": OUTPUT}])
        with job_in(tree) as pid:
            found = check(here, head)
        refused_with(found, ["a job you started is still running", f"{pid} sleep 60"])
        assert_that(check(here, head).out, equal_to("ok\n"))

    def test_a_head_no_worktree_holds_is_refused(self) -> None:
        """The hand-back names a head the worker does not have."""
        here, _, _ = made()
        refused_with(check(here, "e" * 40), ["no worktree of the clone is at head"])

    def test_a_hand_back_that_names_no_head_is_not_judged_by_a_checkout(self) -> None:
        """Only the earlier rules apply."""
        here = world.make_world()
        found = run_check(here, "PR 5\nDeviations: none\n")
        assert_that((found.code, found.out), equal_to((0, "ok\n")))


class TestReaders(unittest.TestCase):
    """The readers of the checkout."""

    def test_a_process_table_is_read_by_the_directory_of_each_process(self) -> None:
        """Parents of this command and unreadable directories are left out."""
        table = "10 1 sh\n11 10 me --run\n12 1 job a b\n13 1 other\nbad row\n"

        def run(command: object, /) -> object:
            return fakes.Output(stdout=table)

        where = {12: "/t/x/sub", 13: "/elsewhere", 10: "/t/x", 11: "/t/x"}
        found = handbackcheck.running_jobs(
            run,  # type: ignore[arg-type]
            pathlib.Path("/t/x"),
            11,
            lambda pid: where.get(pid, ""),
        )
        assert_that(found, equal_to(["12 job a b"]))

    def test_the_directory_of_a_process_that_is_gone_is_empty(self) -> None:
        """No such process."""
        assert_that(handbackcheck.proc_cwd(2**22 + 12345), equal_to(""))
        assert_that(handbackcheck.proc_cwd(os.getpid()) != "", equal_to(True))

    def test_a_git_that_fails_finds_no_worktree(self) -> None:
        """A failing listing, or a command that cannot start, says there is none."""
        for error in (subprocess.CalledProcessError(1, "git"), OSError("no git")):

            def run(command: object, /) -> object:
                raise error

            found = handbackcheck.worktree_at(
                run,  # type: ignore[arg-type]
                pathlib.Path("/t/x"),
                "a" * 40,
            )
            assert_that(found, equal_to(None))
