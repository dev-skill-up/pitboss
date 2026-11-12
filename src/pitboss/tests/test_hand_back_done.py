"""A hand-back is sent once, after its jobs ended, with the Plan check posted."""

import json
import unittest
from typing import Mapping, Sequence

from .. import handbackcheck, handbackrecord, plancheck, plandigest
from . import fakes, world
from .handbackrun import hand_back, processes
from .handbackworld import BASE, ready, unposted
from .cleanworld import absent, same

HEAD = "a" * 40
OTHER = "b" * 40
BODY = (
    f"Fixes #7\n\n## Plan\nthe plan\n\n$ echo hi\n\n## Execution\nx\n\nHead: {HEAD}\n"
)
JOB = "sleep 100"


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
        before = handbackrecord.recorded(git, HEAD)
        handbackrecord.record(git, HEAD)
        after = [handbackrecord.recorded(git, each) for each in (HEAD, OTHER)]
        same([before, *after], [False, True, False])

    def test_the_command_refuses_a_running_job_then_accepts_once(self) -> None:
        """A job in the worktree first; then ok; then the same head again."""
        here = ready(world.make_world())
        busy = processes(fakes.directory(), {7: here.clone.resolve()})
        quiet = processes(fakes.directory(), {})
        done = [
            hand_back(here, busy),
            hand_back(here, quiet, "--pr", "7"),
            hand_back(here, quiet),
        ]
        shown = [(each.code, each.out) for each in done]
        same(shown[0][0], 1)
        same("a job you started is still running: 7 sleep" in shown[0][1], True)
        same(shown[1], (0, "ok\n"))
        same(shown[2][0], 1)
        same("was already accepted" in shown[2][1], True)

    def test_a_refusal_for_a_missing_line_records_nothing(self) -> None:
        """No `Deviations:` line: refused; with it: ok; once more: the second one."""
        here = ready(world.make_world())
        quiet = processes(fakes.directory(), {})
        done = [
            hand_back(here, quiet, text="no line\n"),
            hand_back(here, quiet),
            hand_back(here, quiet),
        ]
        same([each.code for each in done], [1, 0, 1])
        same("NOT STARTED" in done[0].out, True)
        same("was already accepted" in done[2].out, True)

    def test_the_default_invocation_checks_the_plan_check(self) -> None:
        """With no `--pr` the branch's PR is found; an unposted check refuses."""
        here = unposted(world.make_world())
        done = hand_back(here, processes(fakes.directory(), {}))
        same((done.code, "not done until the Plan check" in done.out), (1, True))

    def test_a_branch_with_no_open_pr_or_an_unreadable_list_is_refused(self) -> None:
        """Never ok without the PR; a list that cannot be read is said."""
        quiet = processes(fakes.directory(), {})
        here = world.make_world()
        unread = hand_back(here, quiet)
        here.bodies[f"{BASE}/pulls?state=open&head=owner:main"] = "[]"
        none = hand_back(here, quiet)
        same((unread.code, none.code), (1, 1))
        same("cannot be read" in unread.out, True)
        same("no open PR of owner/project holds" in none.out, True)

    def test_a_directory_that_is_no_worktree_is_refused(self) -> None:
        """`--repo` names something git cannot read."""
        here = world.make_world()
        done = hand_back(
            here, processes(fakes.directory(), {}), "--repo", "/nonexistent"
        )
        same("is not a git worktree" in done.out, True)

    def test_the_repo_option_judges_another_worktree(self) -> None:
        """The worktree's own branch and head are read, wherever the command runs."""
        here = world.make_world()
        other = fakes.add_worktree(here.clone, "other-work")
        done = hand_back(ready(here, other), processes(fakes.directory(), {}))
        same(done.code, 1)
        done = hand_back(here, processes(fakes.directory(), {}), "--repo", str(other))
        same((done.code, done.out), (0, "ok\n"))


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
