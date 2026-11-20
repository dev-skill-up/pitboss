"""Test doubles: a fake GitHub behind ``gh api``, and real git in temp dirs."""

import dataclasses
import os
import json
import pathlib
import re
import subprocess
from typing import (
    Callable,
    Iterable,
    Mapping,
    MutableMapping,
    MutableSequence,
    Protocol,
    Sequence,
)

from .. import config, configfile, ghapi
from . import captured, fullpull, repositories, worldreads

HEAD = "a" * 40
PLAN_AND_EXECUTION = "## Plan\nthe plan\n\n## Execution\nthe work\n"
OLDER = "b" * 40
NOT_FOUND = 127
# a window of tickets' order and time (keyword: ticket-window): the list is whole
ASKED_BY_THE_WINDOW = re.compile(r"&sort=created&direction=asc|&since=[^&]*")
REFUSED = object()  # a body that fails like a path with none, in a world that has one
Answers = Mapping[str, int]
NO_STATUS: Mapping[str, object] = {"statuses": []}
TRACEFS_FOUND: Answers = {"grep": 0, "mount": 1}
# the git helpers are in ``repositories``, which imports nothing of pitboss
IDENTITY = repositories.IDENTITY
run_git = repositories.run_git
commit_file = repositories.commit_file
directory = repositories.directory
push = repositories.push
add_worktree = repositories.add_worktree


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Output:
    """A finished fake process.

    Attributes:
        stdout: its output.
        returncode: its exit status.
    """

    stdout: str
    returncode: int = 0


class Processes(Protocol):
    """What runs the commands' processes."""

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> Output:
        """Run a command.

        Args:
            cmdargs: the command line.
            **kwargs: what gather passes to ``subprocess.run``.

        Returns:
            The finished process.
        """


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FakeProcesses:
    """Answers ``gh api`` from canned bodies, and runs the rest, git too, for real.

    Attributes:
        bodies: each ``gh api`` path (or ``POST`` path) and its JSON body (a
            string is returned as it is, as a job's log is);
            a missing path fails like ``gh`` does on a 404.
        calls: every command line run, in order.
        answers: the exit status of each program that is not run at all (the
            machine's tracefs check and mount, ``curl``, ``gh``); 127 is a
            program not found. ``git`` is never one of them: a test that needs
            git to fail gives it a repository that makes it fail.
        cwd: where the commands that are run for real run; None is the
            directory of the test process.
        path: the ``PATH`` they run with; None is the machine's (a test of a
            machine with no git gives a directory with no programs).
    """

    bodies: MutableMapping[str, object]
    calls: MutableSequence[Sequence[str]] = dataclasses.field(default_factory=list)
    answers: Mapping[str, int] = dataclasses.field(default_factory=dict)
    cwd: pathlib.Path | None = None
    path: str | None = None

    def __call__(
        self, cmdargs: Sequence[str], /, *args: object, **kwargs: object
    ) -> Output:
        """Run a command.

        Args:
            cmdargs: the command line.
            *args: ignored.
            **kwargs: ignored (what gather passes to ``subprocess.run``).

        Returns:
            The finished process.

        Raises:
            subprocess.CalledProcessError: for a path with no body.
        """
        command = list(cmdargs)
        self.calls.append(command)
        if command[0] in self.answers:
            return answer(self.answers[command[0]], command)
        if command[:2] != ["gh", "api"] and command[0] != "curl":  # PyPI (#103)
            return run_for_real(command, self.cwd, self.path)
        path, body = canned(self.bodies, command)
        if body is None or body is REFUSED:
            raise subprocess.CalledProcessError(
                1, command, output="", stderr=f"gh: not found: {path} (HTTP 404)\n"
            )
        return Output(stdout=body if isinstance(body, str) else json.dumps(body))


def canned(bodies: Mapping[str, object], command: Sequence[str]) -> tuple[str, object]:
    """What a world cans for a ``gh api`` command (a list read as one page: page 1).

    Args:
        bodies: the world's bodies.
        command: the command.

    Returns:
        The path asked for, and its body (None when the world cans none).
    """
    path = command[-1] if command[2] != "-X" else f"{command[3]} {command[-1]}"
    path = ASKED_BY_THE_WINDOW.sub("", path)  # a world cans a list whole
    first = f"{path}&page=1" if "per_page=100" in path else page(path)
    found = None if path in bodies else worldreads.org_searched(bodies, path)
    found = found or bodies.get(path, bodies.get(first, worldreads.none_listed(path)))
    return path, fullpull.complete(path, worldreads.listed_whole(bodies, path, found))


def run_for_real(
    command: Sequence[str], cwd: pathlib.Path | None, path: str | None
) -> Output:
    """Run a command, ``git`` included, on the machine.

    Args:
        command: the command line.
        cwd: where it runs; None is the directory of the test process.
        path: its ``PATH``; None is the machine's.

    Returns:
        The finished process.
    """
    env = None if path is None else {**os.environ, "PATH": path}
    done = captured.run(command, cwd=cwd, env=env)
    return Output(stdout=done.stdout)


def answer(status: int, command: Sequence[str]) -> Output:
    """What a program that is not run answers.

    Args:
        status: its exit status; 127 is a program that is not found.
        command: the command line.

    Returns:
        The finished process.

    Raises:
        ValueError: for ``git``, which is never answered.
        FileNotFoundError: for 127.
        subprocess.CalledProcessError: for any other status but 0.
    """
    if command[0] == "git":
        raise ValueError("git is run for real; give it a repository that fails")
    if status == NOT_FOUND:
        raise FileNotFoundError(command[0])
    if status:
        raise subprocess.CalledProcessError(
            status, command, output="", stderr=f"fatal: {command[0]} refused\n"
        )
    return Output(stdout="")


def github(bodies: MutableMapping[str, object]) -> ghapi.GitHub:
    """A fake API whose reads and changes both answer from ``bodies``.

    Args:
        bodies: the canned bodies.

    Returns:
        The API.
    """
    fake = FakeProcesses(bodies=bodies)
    return ghapi.GitHub(run=fake, mutate=fake)


def page(path: str, number: int = 1) -> str:
    """The path ``ghapi.pages`` asks for.

    Args:
        path: the list's path.
        number: the page.

    Returns:
        The paged path.
    """
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}per_page=100&page={number}"


def listed_row(
    bodies: MutableMapping[str, object], repo: str, number: int, **fields: object
) -> None:
    """Give a PR's row of a repository's open listing fields, as GitHub's carries.

    Args:
        bodies: the canned answers.
        repo: the repository's ``repos/owner/name`` path.
        number: the PR.
        **fields: the fields the row gets (its body, its head).
    """
    listing = bodies[page(f"{repo}/pulls?state=open")]
    assert isinstance(listing, list)
    listing[:] = [
        {**row, **fields} if row.get("number") == number else row for row in listing
    ]


def pull_body(number: int, **changes: object) -> MutableMapping[str, object]:
    """A PR's JSON.

    Args:
        number: its number.
        **changes: fields to replace.

    Returns:
        The JSON.
    """
    body: dict[str, object] = {
        "number": number,
        "title": f"PR {number}",
        "created_at": "2026-10-01T00:00:00+00:00",
        "draft": False,
        "user": {"login": "pitboss-bot"},
        "body": PLAN_AND_EXECUTION,
        "head": {"sha": HEAD, "ref": f"branch-{number}"},
        "base": {"ref": "main"},
        "mergeable_state": "clean",
        "auto_merge": None,
        "state": "open",
        "merged_at": None,
    }
    body.update(changes)
    return body


def settings(directory: pathlib.Path, extra: str = "") -> config.Config:
    """A configuration for ``owner/project`` with its clone under ``directory``.

    Args:
        directory: the workspace.
        extra: more TOML, appended.

    Returns:
        The configuration.
    """
    path = directory / "project.toml"
    path.write_text(
        "[project]\n"
        'owner = "owner"\n'
        'repository = "project"\n'
        f'main_clone = "{directory / "project"}"\n'
        f'workspace = "{directory}"\n' + extra
    )
    return configfile.load(str(path), directory)


def make_unfetchable(workspace: pathlib.Path, name: str) -> pathlib.Path:
    """Make a checkout whose ``origin`` cannot be fetched.

    Args:
        workspace: where.
        name: its directory's name.

    Returns:
        The checkout.
    """
    checkout = workspace / name
    run_git(workspace, "init", "-q", str(checkout))
    run_git(checkout, "remote", "add", "origin", "/nowhere")
    return checkout


def write(path: pathlib.Path, text: str) -> None:
    """Write a file, making its directory.

    Args:
        path: the file.
        text: its content.
    """
    os.makedirs(path.parent, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def calls_with(calls: Sequence[Sequence[str]], word: str) -> Sequence[Sequence[str]]:
    """The calls that have a word.

    Args:
        calls: the calls made.
        word: the word (``-X``, ``POST``).

    Returns:
        Those calls, in order.
    """
    return [call for call in calls if call.count(word)]


def bodies_under(
    prefix: str, bodies: Iterable[tuple[str, object]]
) -> MutableMapping[str, object]:
    """Bodies for the first pages of lists under one prefix.

    Args:
        prefix: the paths' common start.
        bodies: each list's path after the prefix, and its body.

    Returns:
        The bodies, by paged path.
    """
    return {page(f"{prefix}/{path}"): body for path, body in bodies}


def error_of(action: Callable[[], object]) -> str:
    """The message of the error an action raises.

    Args:
        action: the action.

    Returns:
        The message, or empty when nothing was raised.
    """
    try:
        action()
    except (ValueError, FileNotFoundError) as error:
        return str(error)
    return ""


def calls_of(api: ghapi.GitHub) -> Sequence[Sequence[str]]:
    """Every command line a fake API ran.

    Args:
        api: an API made by ``github``.

    Returns:
        The command lines, in order.
    """
    runner = api.run
    return runner.calls if isinstance(runner, FakeProcesses) else []


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FakeTranscripts:
    """Transcripts held in a dict (``_texts``: each agent id and its text)."""

    _texts: Mapping[str, str]

    def names(self) -> Sequence[str]:
        """List the agents.

        Returns:
            The ids.
        """
        return sorted(self._texts)

    def read(self, agent: str) -> str:
        """Read a transcript.

        Args:
            agent: the id.

        Returns:
            The text.
        """
        return self._texts[agent]


def seed_ledger(path: pathlib.Path, names: Sequence[str]) -> None:
    """Write a ledger of empty slots, as the owner would create it.

    Args:
        path: the ledger file.
        names: the slot names, each on the model of the same position in
            ``small``, ``large``.
    """
    models = ("small", "large")
    rows = [f'{{"name": "{n}", "model": "{m}"}}' for n, m in zip(names, models)]
    path.write_text('{"slots": [' + ", ".join(rows) + '], "failed": {}}')
