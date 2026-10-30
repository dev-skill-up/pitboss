"""A whole project for the command tests: a fake GitHub, a real clone."""

import argparse
import contextlib
import dataclasses
import datetime
import io
import pathlib
from typing import Mapping, MutableMapping, MutableSequence, Sequence

from gather import commands as gather_commands

from .. import cli_parser
from . import fakes

FUTURE = "2030-01-01T00:00:00+00:00"
START = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
PROJECT = "repos/owner/project"
LIBRARY = "repos/owner/lib"
EXTRA = """
[libraries]
repositories = ["lib", "gone"]
no_auto_merge = ["lib"]

[review]
gated = ["gated"]

[clean]
min_free_gib = 0

[slots]
ledger = "{ledger}"
models = ["small", "large"]
priority_labels = ["urgent"]
default = [{{name = "tiny", model = "small"}}, {{name = "big", model = "large"}}]
"""
GREEN = {"id": 7, "name": "build", "status": "completed", "conclusion": "success"}
RED = {"id": 8, "name": "test", "status": "completed", "conclusion": "failure"}
RED_JOB = "repos/owner/project/actions/jobs/8"
RED_RUN = "repos/owner/project/check-runs/8"
RED_NOTES = "repos/owner/project/check-runs/8/annotations?per_page=20"
RED_BODIES: Mapping[str, object] = {
    RED_JOB: {
        "steps": [
            {"name": "Set up job", "conclusion": "success"},
            {"name": "Run bats check", "conclusion": "failure"},
        ]
    },
    RED_RUN: {"output": {"title": "check failed", "summary": "1 error"}},
    RED_NOTES: [
        {
            "path": "src/a.bats",
            "start_line": 3,
            "message": "bad\ntype",
            "annotation_level": "failure",
        },
        {
            "path": ".github",
            "start_line": 2,
            "message": "Node 20 is deprecated",
            "annotation_level": "warning",
        },
    ],
}
APPROVAL = {
    "state": "APPROVED",
    "commit_id": fakes.HEAD,
    "author_association": "MEMBER",
    "submitted_at": "2026-10-02T00:00:00Z",
}
COMMENT = {
    "body": f"## Review\nReviewed: {fakes.HEAD}\nVerdict: approved\n",
    "author_association": "MEMBER",
    "created_at": "2026-10-02T00:00:00Z",
}
TICKET = {
    "number": 9,
    "title": "A ticket",
    "created_at": "2026-09-01T00:00:00+00:00",
    "labels": [{"name": "urgent"}],
}
QUEUE_RUNS = {
    "workflow_runs": [
        {
            "id": 11,
            "status": "queued",
            "conclusion": None,
            "created_at": "2029-12-31T23:11:00+00:00",
            "head_branch": "gh-readonly-queue/main/pr-2-old",
        },
        {
            "id": 12,
            "status": "in_progress",
            "conclusion": None,
            "created_at": "2029-12-31T23:12:00+00:00",
            "head_branch": "gh-readonly-queue/main/pr-2-new",
        },
    ]
}
REPOSITORY_BODIES: MutableMapping[str, object] = {
    PROJECT: {},
    LIBRARY: {},
    fakes.page(f"{PROJECT}/pulls?state=open"): [
        {"number": 1},
        {"number": 2},
        {"number": 3},
    ],
    fakes.page(f"{LIBRARY}/pulls?state=open"): [{"number": 4}],
    fakes.page(f"{PROJECT}/actions/runs?event=merge_group"): QUEUE_RUNS,
    fakes.page(f"{LIBRARY}/actions/runs?event=merge_group"): {"workflow_runs": []},
    fakes.page(f"{PROJECT}/actions/runs/11/jobs"): {"jobs": [{"status": "queued"}]},
    fakes.page(f"{PROJECT}/actions/runs/12/jobs"): {"jobs": []},
    f"POST {PROJECT}/actions/runs/11/cancel": {},
    fakes.page(f"{PROJECT}/pulls?state=all"): [
        {"head": {"ref": "merged-work"}, "state": "closed", "merged_at": "x"}
    ],
    fakes.page(f"{LIBRARY}/pulls?state=all"): [],
    fakes.page(f"{PROJECT}/issues?state=open&labels=urgent"): [TICKET],
    fakes.page(f"{LIBRARY}/issues?state=open&labels=urgent"): [],
}
PULLS: Sequence[tuple[str, int, object, str]] = [
    ("owner/project", 1, [RED], "dirty"),
    ("owner/project", 2, [GREEN], "clean"),
    ("owner/project", 3, [GREEN], "clean"),
    ("owner/lib", 4, [GREEN], "clean"),
]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class World:
    """A workspace with a clone, a finished worktree, a config and a fake GitHub.

    Attributes:
        workspace: the workspace.
        clone: the main clone.
        worktree: a worktree whose PR merged.
        ledger: the slot ledger.
        config: the configuration file.
        bodies: the fake GitHub's bodies (change them to change GitHub).
        calls: every command line the commands ran.
        processes: what the commands run processes with.
    """

    workspace: pathlib.Path
    clone: pathlib.Path
    worktree: pathlib.Path
    ledger: pathlib.Path
    config: str
    bodies: MutableMapping[str, object]
    calls: MutableSequence[Sequence[str]]
    processes: fakes.Processes


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Result:
    """What a command did.

    Attributes:
        out: its standard output.
        err: its standard error.
        code: its exit code.
    """

    out: str
    err: str
    code: object


def pull_bodies(
    slug: str, number: int, checks: object, state: str
) -> MutableMapping[str, object]:
    """One open PR: details, comments, reviews and its head's checks.

    PR 2 has a GitHub approval of its head; the library's PR a comment one.

    Args:
        slug: its repository.
        number: its number.
        checks: its head's check runs.
        state: its merge state.

    Returns:
        The canned bodies.
    """
    library = slug.endswith("lib")
    head = fakes.HEAD if number == 2 or library else str(number) * 40
    prefix = f"repos/{slug}"
    branch = {"sha": head, "ref": f"branch-{number}"}
    details = fakes.pull_body(number, head=branch, mergeable_state=state)
    pages = [
        (f"issues/{number}/comments", [COMMENT] if library else []),
        (f"pulls/{number}/reviews", [APPROVAL] if number == 2 else []),
        (f"commits/{head}/check-runs", {"check_runs": checks}),
    ]
    found = fakes.bodies_under(prefix, pages)
    found[f"{prefix}/pulls/{number}"] = details
    return found


def unread_first(here: World, body: str = "") -> None:
    """Make PR 1 unreadable: its check-runs call fails (#101).

    Args:
        here: the world.
        body: the text of PR 1's body.
    """
    head = "1" * 40
    branch = {"sha": head, "ref": "branch-1"}
    here.bodies[f"{PROJECT}/pulls/1"] = fakes.pull_body(1, body=body, head=branch)
    del here.bodies[fakes.page(f"{PROJECT}/commits/{head}/check-runs")]


def bodies() -> MutableMapping[str, object]:
    """The fake GitHub of the tests.

    Returns:
        The canned bodies.
    """
    found = dict(REPOSITORY_BODIES)
    for slug, number, checks, state in PULLS:
        found.update(pull_bodies(slug, number, checks, state))
    found.update(RED_BODIES)
    return found


def configure(workspace: pathlib.Path) -> pathlib.Path:
    """Write the configuration of a workspace.

    Args:
        workspace: the workspace.

    Returns:
        The slot ledger's path.
    """
    ledger = workspace / "ledger.json"
    fakes.settings(workspace, EXTRA.format(ledger=ledger))
    fakes.seed_ledger(ledger, ("tiny", "big"))
    return ledger


def make_world(answers: fakes.Answers = fakes.TRACEFS_FOUND) -> World:
    """Make a world.

    Args:
        answers: the exit status of the tracefs check (``grep``) and of the
            mount; nothing is mounted on the machine.

    Returns:
        The world.
    """
    workspace = fakes.directory()
    clone = fakes.make_repository(workspace)
    worktree = fakes.add_worktree(clone, "merged-work")
    fakes.push(worktree)
    ledger = configure(workspace)
    processes = fakes.FakeProcesses(bodies=bodies(), answers=answers)
    return World(
        workspace=workspace,
        clone=clone,
        worktree=worktree,
        ledger=ledger,
        config=str(workspace / "project.toml"),
        bodies=processes.bodies,
        calls=processes.calls,
        processes=processes,
    )


def parser() -> argparse.ArgumentParser:
    """The command line parser of every pitboss command.

    Returns:
        The parser.
    """
    return cli_parser.make_parser()


def shell_env(world: World, directory: pathlib.Path | None) -> Mapping[str, str]:
    """The environment a command runs with.

    Args:
        world: the world.
        directory: the directory it runs in; the workspace when None.

    Returns:
        The environment, whose ``PWD`` is that directory.
    """
    return {"PWD": str(directory or world.workspace)}


def invoke(world: World, *argv: str, directory: pathlib.Path | None = None) -> Result:
    """Run ``pitboss`` with arguments.

    Args:
        world: the world.
        *argv: the arguments.
        directory: the directory it runs in (its ``PWD``); the workspace when
            None.

    Returns:
        What it did.
    """
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = exit_code(world, ["pitboss", *argv], shell_env(world, directory))
    return Result(out=out.getvalue(), err=err.getvalue(), code=code)


def exit_code(world: World, argv: Sequence[str], env: Mapping[str, str]) -> object:
    """Run the command line and say how it exited.

    Args:
        world: the world.
        argv: the whole command line.
        env: the environment it runs with.

    Returns:
        The code it exited with; 0 when it returned.
    """
    try:
        gather_commands.run_maybe_dry(
            parser=parser(),
            argv=list(argv),
            env=env,
            sp_run=world.processes,
        )
    except SystemExit as exit_error:
        return exit_error.code
    return 0


def again(here: World, *argv: str, directory: pathlib.Path | None = None) -> Result:
    """Run ``pitboss`` in a world, with the config after the command.

    Args:
        here: the world.
        *argv: the command, then the arguments after the config.
        directory: the directory it runs in; the workspace when None.

    Returns:
        What the command did.
    """
    return invoke(here, argv[0], here.config, *argv[1:], directory=directory)


def project_page(path: str) -> str:
    """The first page of a list of the project's.

    Args:
        path: the list's path under the project's repository.

    Returns:
        The paged path.
    """
    return fakes.page(f"{PROJECT}/{path}")
