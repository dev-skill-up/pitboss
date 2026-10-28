"""A repository whose workflow has red runs of every kind, as canned bodies."""

import dataclasses
import json
from typing import Mapping, MutableMapping, Sequence

from . import fakes

ALPHA = "a" * 40
BRAVO = "b" * 40
CHARLIE = "c" * 40
DELTA = "d" * 40
ECHO = "e" * 40
FOXTROT = "f" * 40
NOW = "2026-10-03T12:00:00+00:00"
STEP_START = "2026-10-01T00:00:10Z"
JOB_START = "2026-10-01T00:00:00Z"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Red:
    """A red run of the scenario, with its failed job and log.

    The run's id is also its time: id 6 was created at 01:00, 7 at 01:10.

    Attributes:
        identifier: the run's id; its job is ten times that.
        branch: its branch.
        sha: its commit.
        log: its failed job's log; ``None`` when GitHub no longer has it.
        pulls: its PRs.
        conclusion: its conclusion.
        event: its event.
        steps: the job's steps, each a name and a conclusion.
        step_end: when each step ended.
        job_end: when the job ended.
    """

    identifier: int
    branch: str
    sha: str
    log: str | None
    pulls: Sequence[int] = ()
    conclusion: str = "failure"
    event: str = "pull_request"
    steps: Sequence[tuple[str, str]] = (("build", "failure"),)
    step_end: str = "2026-10-01T00:09:00Z"
    job_end: str = "2026-10-01T00:10:00Z"


GDB = "FAILED gdb test 3 failed"
UNLISTED = "##[error]fixture not listed in any group"
REDS = (
    Red(
        identifier=4,
        branch="release",
        sha=ALPHA,
        log="##[error]versionCode 12 already exists\n",
        steps=(("publish", "failure"),),
    ),
    Red(
        identifier=5,
        branch="anchor",
        sha=FOXTROT,
        log="##[error]stale anchor in docs",
        steps=(("docs", "failure"),),
        step_end="2026-10-01T00:00:30Z",
        job_end="2026-10-01T00:30:00Z",
    ),
    Red(
        identifier=6,
        branch="feat",
        sha=ALPHA,
        pulls=(7,),
        log="2026-10-01T00:05:00.1Z start\n2026-10-01T00:06:00.1Z ##[error]FAILED"
        " tests/test_x.py::t - 1 != 2\n",
        steps=(("setup", "success"), ("pytest", "failure")),
    ),
    Red(
        identifier=7,
        branch="feat",
        sha=ALPHA,
        pulls=(7,),
        log=None,
        steps=(("setup", "success"), ("pytest", "failure")),
    ),
    Red(
        identifier=8,
        branch="g1",
        sha=BRAVO,
        log=f"go\n{GDB}\n",
        steps=(("gdb", "failure"),),
    ),
    Red(
        identifier=9,
        branch="g2",
        sha=CHARLIE,
        log=f"go\n{GDB}\n",
        steps=(("gdb", "failure"),),
    ),
    Red(
        identifier=10,
        branch="dependabot/npm/x",
        sha=DELTA,
        log="##[error]boom\n",
        steps=(("install", "failure"),),
    ),
    Red(
        identifier=11,
        branch="reg",
        sha=ECHO,
        log="##[error]npm ERR! ECONNRESET\n",
        conclusion="timed_out",
        steps=(("install", "failure"),),
    ),
    Red(
        identifier=12,
        branch="nostep",
        sha=FOXTROT,
        log="",
        steps=(("setup", "success"),),
    ),
    Red(identifier=13, branch="noline", sha=FOXTROT, log="all fine\nnothing\n"),
    Red(
        identifier=14,
        branch="queue",
        sha=ALPHA,
        log="Error: queue\n",
        event="merge_group",
        job_end="",
    ),
    Red(
        identifier=15,
        branch="m",
        sha=BRAVO,
        pulls=(8,),
        log=f"{UNLISTED}\n",
        steps=(("gdb", "failure"),),
    ),
    Red(
        identifier=16,
        branch="n",
        sha=CHARLIE,
        pulls=(9,),
        log=f"{UNLISTED}\n",
        steps=(("gdb", "failure"),),
    ),
    Red(
        identifier=17,
        branch="reg2",
        sha=ECHO,
        log=f"{UNLISTED}\n",
        steps=(("install", "failure"),),
    ),
)
BRANCH_PAGES = ("g1", "g2", "dependabot%2Fnpm%2Fx", "reg", "nostep", "noline")
MORE_BRANCHES = ("queue", "m", "n", "reg2", "running", "anchor", "release")


def run(slug: str, identifier: int, conclusion: str | None) -> Mapping[str, object]:
    """A green or running workflow run's JSON.

    Args:
        slug: its repository.
        identifier: its id (also its time).
        conclusion: its conclusion.

    Returns:
        The JSON.
    """
    return _red_run(
        slug, Red(identifier=identifier, branch="feat", sha=ALPHA, log=None), conclusion
    )


def _red_run(slug: str, red: Red, conclusion: str | None) -> Mapping[str, object]:
    identifier = red.identifier
    hour, minute = identifier // 6, identifier % 6 * 10
    return {
        "id": identifier,
        "html_url": f"https://github.com/{slug}/actions/runs/{identifier}",
        "status": "completed" if conclusion else "in_progress",
        "conclusion": conclusion,
        "created_at": f"2026-10-01T{hour:02d}:{minute:02d}:00Z",
        "updated_at": f"2026-10-01T{hour:02d}:{minute + 5:02d}:00Z",
        "head_branch": red.branch,
        "head_sha": red.sha,
        "pull_requests": [{"number": number} for number in red.pulls],
        "event": red.event,
    }


def _failed_job(slug: str, red: Red) -> Mapping[str, object]:
    steps = [
        {
            "number": number,
            "name": name,
            "conclusion": conclusion,
            "started_at": STEP_START,
            "completed_at": red.step_end,
        }
        for number, (name, conclusion) in enumerate(red.steps, start=1)
    ]
    identifier = red.identifier * 10
    return {
        "id": identifier,
        "name": "test",
        "conclusion": "timed_out" if red.conclusion == "timed_out" else "failure",
        "html_url": f"https://github.com/{slug}/actions/runs/1/job/{identifier}",
        "started_at": JOB_START,
        "completed_at": red.job_end,
        "steps": steps,
    }


def commit(sha: str, date: str, message: str, parents: int = 1) -> Mapping[str, object]:
    """A PR commit's JSON.

    Args:
        sha: its SHA.
        date: its committer date.
        message: its message.
        parents: how many parents.

    Returns:
        The JSON.
    """
    return {
        "sha": sha,
        "commit": {"message": message, "committer": {"date": date}},
        "parents": [{}] * parents,
    }


def _pr_body(number: int, merged_at: str | None) -> Mapping[str, object]:
    return {
        "number": number,
        "title": f"PR {number}",
        "html_url": f"https://example.org/pull/{number}",
        "merged_at": merged_at,
        "state": "closed" if merged_at or number == 9 else "open",
    }


def _all_runs(slug: str) -> MutableMapping[str, object]:
    prefix = f"repos/{slug}/actions/workflows/ci.yml/runs"
    runs = [
        *(_red_run(slug, red, red.conclusion) for red in REDS),
        run(slug, 18, "success"),
        run(slug, 19, None),
    ]
    found: MutableMapping[str, object] = {fakes.page(prefix): {"workflow_runs": runs}}
    later = {"workflow_runs": [run(slug, 7, "failure"), run(slug, 20, "success")]}
    found[fakes.page(f"{prefix}?branch=feat")] = later
    for branch in (*BRANCH_PAGES, *MORE_BRANCHES):
        found[fakes.page(f"{prefix}?branch={branch}")] = {"workflow_runs": []}
    return found


def _all_jobs(slug: str) -> MutableMapping[str, object]:
    prefix = f"repos/{slug}/actions"
    found: MutableMapping[str, object] = {}
    for red in REDS:
        found[fakes.page(f"{prefix}/runs/{red.identifier}/jobs")] = {
            "jobs": [_failed_job(slug, red)]
        }
        if red.log is not None:
            found[f"{prefix}/jobs/{red.identifier * 10}/logs"] = red.log
    return found


def _all_prs(slug: str) -> MutableMapping[str, object]:
    prefix = f"repos/{slug}"
    return {
        f"{prefix}/pulls/7": _pr_body(7, "2026-10-02T00:00:00Z"),
        f"{prefix}/pulls/8": _pr_body(8, None),
        f"{prefix}/pulls/9": _pr_body(9, None),
        fakes.page(f"{prefix}/pulls/7/commits"): [
            commit(ALPHA, "2026-10-01T00:20:00Z", "first"),
            commit(BRAVO, "2026-10-01T02:30:00Z", "fix the test\n\nbody"),
        ],
        fakes.page(f"{prefix}/pulls/8/commits"): [
            commit(BRAVO, "2026-10-01T02:00:00Z", "first"),
            commit(CHARLIE, "2026-10-01T03:00:00Z", "Merge main", parents=2),
        ],
        fakes.page(f"{prefix}/pulls/9/commits"): [
            commit(DELTA, "2026-10-01T02:00:00Z", "other")
        ],
        f"{prefix}/commits/{BRAVO}": {"files": [{"filename": "tests/test_x.py"}]},
        f"{prefix}/commits/{CHARLIE}": {"files": []},
    }


def _p0_issue(number: int, title: str, labels: Sequence[str]) -> Mapping[str, object]:
    return {
        "number": number,
        "title": title,
        "created_at": "2026-10-01T05:00:00Z",
        "labels": [{"name": name} for name in labels],
        "body": "gdb" if number == 30 else "",
    }


def _all_issues(slug: str) -> MutableMapping[str, object]:
    prefix = f"repos/{slug}"
    cites = {
        "body": "runs 8 and 9 and 81",
        "author_association": "MEMBER",
        "created_at": "2026-10-01T06:00:00Z",
    }
    return {
        fakes.page(f"{prefix}/issues?state=open&labels=p0"): [
            _p0_issue(30, "gdb test fails", ["p0", "quarantined"]),
            _p0_issue(31, "unrelated", ["p0"]),
            _p0_issue(32, "release", ["p0"]),
        ],
        fakes.page(f"{prefix}/issues/30/comments"): [cites],
        fakes.page(f"{prefix}/issues/31/comments"): [],
        fakes.page(f"{prefix}/issues/32/comments"): [
            {**cites, "body": "run 12", "created_at": "2026-10-03T06:00:00Z"}
        ],
    }


def bodies(slug: str) -> MutableMapping[str, object]:
    """The canned GitHub of the scenario, for a repository.

    Run 5 is a stale anchor that CI showed in 30 seconds and kept a job
    running for 30 minutes. Runs 6 and 7 are one commit on PR 7 (7's log is
    gone), 8 and 9 share a test and a ticket, 10 a pinned branch, 11 the
    registry, 12 a run with no failed step, 13 a log with no error line, 14 a
    merge-queue run, 15 and 16 PRs whose fixes are a merge of main and
    nothing; 18 is green and 19 is running.

    Args:
        slug: the repository.

    Returns:
        The bodies.
    """
    found: MutableMapping[str, object] = {f"repos/{slug}": {}}
    for part in (_all_runs, _all_jobs, _all_prs, _all_issues):
        found.update(part(slug))
    return found


def _line(command: str) -> str:
    block = {"type": "tool_use", "name": "Bash", "input": {"command": command}}
    return json.dumps({"message": {"content": [block]}})


def transcript(branch: str, sha: str) -> str:
    """A worker's transcript that pushes a branch.

    Args:
        branch: the branch.
        sha: the commit.

    Returns:
        The JSON lines.
    """
    return "\n".join(
        [
            "not json",
            json.dumps({"message": {"content": "plain text"}}),
            json.dumps({"message": {"content": ["text", {"name": "Read"}]}}),
            _line("python -m pytest tests/test_x.py"),
            json.dumps({"result": f"committed {sha[:7]} on {branch}"}),
            _line(f"git push origin {branch}"),
            _line("echo after"),
        ]
    )
