"""A hand-back is sent once, after its jobs ended, with the Plan check posted."""

import json
import os
import pathlib
import unittest
from typing import Mapping, Sequence

from .. import handbackcheck, plancheck, plandigest
from . import fakes, world
from .cleanworld import absent, same
from .test_deviations import saved

HANDED = "Deviations: none\n"
HEAD = "a" * 40
OTHER = "b" * 40
BODY = (
    f"Fixes #7\n\n## Plan\nthe plan\n\n$ echo hi\n\n## Execution\nx\n\nHead: {HEAD}\n"
)
JOB = "sleep 100"


def processes(top: pathlib.Path, working: Mapping[int, pathlib.Path]) -> pathlib.Path:
    """A directory of process entries: a shell (5, child of 4) and the jobs.

    Args:
        top: where to make it.
        working: the working directory of each job by process id.

    Returns:
        The directory.
    """
    proc = top / "proc"
    own = [(4, 1, top), (5, 4, top)]
    for pid, parent, cwd in (*own, *[(p, 4, w) for p, w in working.items()]):
        entry = proc / str(pid)
        entry.mkdir(parents=True)
        (entry / "stat").write_text(f"{pid} (name) S {parent} 0\n", encoding="utf-8")
        (entry / "cmdline").write_bytes(b"sleep\x00100\x00")
        os.symlink(cwd, entry / "cwd")
    (proc / "self").mkdir()
    return proc


def hand_back(here: world.World, proc: pathlib.Path, *more: str) -> world.Result:
    """Run ``hand-back-check`` on a deviations file against a process directory.

    Args:
        here: the world.
        proc: the directory of process entries.
        *more: more arguments.

    Returns:
        What it printed and its status.
    """
    args = ("hand-back-check", saved(HANDED), "--config", here.config)
    return world.invoke(here, *args, "--processes", str(proc), *more)


class TestJobs(unittest.TestCase):
    """A process that runs in the worktree and is not the check is a job."""

    def test_only_a_process_below_the_worktree_is_a_job(self) -> None:
        """The check and its parents are not; one elsewhere is not."""
        top = fakes.directory()
        for leaf in ("tree/sub", "other"):
            (top / leaf).mkdir(parents=True)
        below = {7: top / "tree" / "sub", 8: top / "other", 9: top / "tree"}
        found = handbackcheck.running_jobs(top / "tree", processes(top, below), 5)
        same(found, [f"7 {JOB}", f"9 {JOB}"])

    def test_the_refusal_names_the_job_and_none_is_no_line(self) -> None:
        """The line says what the worker does about it."""
        said = handbackcheck.jobs_line([f"7 {JOB}", f"9 {JOB}"])
        wanted = ["a job you started is still running: 7 sleep", "and 1 more"]
        same((absent(said, wanted), handbackcheck.jobs_line([])), ([], ""))

    def test_a_process_with_no_command_line_is_still_named(self) -> None:
        """An unreadable command line is said, not skipped."""
        top = fakes.directory()
        proc = processes(top, {7: top})
        (proc / "7" / "cmdline").unlink()
        same(handbackcheck.running_jobs(top, proc, 5), ["7 (unreadable)"])


class TestOnce(unittest.TestCase):
    """The hand-back of a head is accepted once."""

    def test_the_record_names_the_heads(self) -> None:
        """Not recorded, recorded, another head, and a directory with no record."""
        git = fakes.directory()
        before = handbackcheck.recorded(git, HEAD)
        handbackcheck.record(git, HEAD)
        after = [handbackcheck.recorded(git, each) for each in (HEAD, OTHER)]
        same([before, *after], [False, True, False])

    def test_the_command_refuses_a_running_job_then_accepts_once(self) -> None:
        """A job in the worktree first; then ok; then the same head again."""
        here = world.make_world()
        busy = processes(fakes.directory(), {7: here.clone.resolve()})
        quiet = processes(fakes.directory(), {})
        done = [hand_back(here, each) for each in (busy, quiet, quiet)]
        shown = [(each.code, each.out) for each in done]
        same(shown[0][0], 1)
        same("a job you started is still running: 7 sleep" in shown[0][1], True)
        same(shown[1], (0, "ok\n"))
        same(shown[2][0], 1)
        same("was already accepted" in shown[2][1], True)

    def test_a_pr_that_does_not_hold_the_head_refuses_the_hand_back(self) -> None:
        """``--pr`` reads the PR and its comments; its head is not the pushed one."""
        here = world.make_world()
        base = "repos/owner/project"
        here.bodies[f"{base}/pulls/7"] = json.dumps(_pull(OTHER, BODY))
        here.bodies[f"{base}/issues/7/comments?per_page=100&page=1"] = "[]"
        done = hand_back(here, processes(fakes.directory(), {}), "--pr", "7")
        same("owner/project#7 holds head" in done.out, True)


def _pull(head: str, body: str) -> Mapping[str, object]:
    return {
        "number": 7,
        "title": "t",
        "created_at": "2026-11-11T00:00:00Z",
        "user": {"login": "x"},
        "body": body,
        "head": {"sha": head, "ref": "b"},
        "base": {"ref": "main"},
    }


def _pulled(
    head: str, body: str, comments: Sequence[Mapping[str, str]]
) -> handbackcheck.Pushed:
    pull = _pull(head, body)
    page = "repos/o/r/issues/7/comments?per_page=100&page=1"
    bodies: dict[str, object] = {
        "repos/o/r/pulls/7": json.dumps(pull),
        page: json.dumps(comments),
    }
    return handbackcheck.Pushed(
        github=fakes.github(bodies),
        slug="o/r",
        number=7,
        head=HEAD,
        trusted=frozenset({"MEMBER"}),
    )


def _check(body: str, refused: Sequence[int] = ()) -> Mapping[str, str]:
    text = plancheck.text(plandigest.section(body), ["row 1: ran"], refused)
    return {
        "body": text,
        "author_association": "MEMBER",
        "created_at": "2026-11-11T00:00:01Z",
        "html_url": "https://example.org/1",
    }


class TestPlanCheckPosted(unittest.TestCase):
    """The hand-back is not done until the Plan check of the head is posted."""

    def test_each_thing_missing_is_a_refusal_and_nothing_missing_is_none(self) -> None:
        """Posted and clean; another head; another body head; none; refused."""
        other = BODY.replace(HEAD, OTHER)
        cases = {
            "clean": (_pulled(HEAD, BODY, [_check(BODY)]), None),
            "head": (_pulled(OTHER, BODY, [_check(BODY)]), "holds head"),
            "body": (_pulled(HEAD, other, [_check(other)]), "no last `Head:`"),
            "unposted": (_pulled(HEAD, BODY, []), "not done until the Plan check"),
            "refused": (_pulled(HEAD, BODY, [_check(BODY, [1])]), "not done until"),
        }
        texts = {
            name: " | ".join(handbackcheck.pull_lines(pushed))
            for name, (pushed, _) in cases.items()
        }
        held = {
            name: (texts[name] == "") if said is None else (said in texts[name])
            for name, (_, said) in cases.items()
        }
        same(held, {name: True for name in cases})
