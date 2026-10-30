"""Test doubles: a fake GitHub behind ``gh api``, and real git in temp dirs."""

import dataclasses
import os
import json
import pathlib
import subprocess
import tempfile
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

HEAD = "a" * 40
OLDER = "b" * 40
NOT_FOUND = 127
Answers = Mapping[str, int]
TRACEFS_FOUND: Answers = {"grep": 0, "mount": 1}
IDENTITY = ("-c", "user.email=t@example.org", "-c", "user.name=T")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Output:
    """A finished fake process.

    Attributes:
        stdout: its output.
    """

    stdout: str


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
    """Answers ``gh api`` from canned bodies, and runs everything else.

    Attributes:
        bodies: each ``gh api`` path (or ``POST`` path) and its JSON body (a
            string is returned as it is, as a job's log is);
            a missing path fails like ``gh`` does on a 404.
        calls: every command line run, in order.
        answers: the exit status of each program that is not run at all (the
            machine's tracefs check and mount); 127 is a program not found.
    """

    bodies: MutableMapping[str, object]
    calls: MutableSequence[Sequence[str]] = dataclasses.field(default_factory=list)
    answers: Mapping[str, int] = dataclasses.field(default_factory=dict)

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> Output:
        """Run a command.

        Args:
            cmdargs: the command line.
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
        if command[:2] != ["gh", "api"]:
            done = subprocess.run(command, check=True, capture_output=True, text=True)
            return Output(stdout=done.stdout)
        path = command[-1] if command[2] != "-X" else "POST " + command[-1]
        if path not in self.bodies:
            raise subprocess.CalledProcessError(
                1, command, output="", stderr=f"gh: not found: {path} (HTTP 404)\n"
            )
        body = self.bodies[path]
        return Output(stdout=body if isinstance(body, str) else json.dumps(body))


def answer(status: int, command: Sequence[str]) -> Output:
    """What a program that is not run answers.

    Args:
        status: its exit status; 127 is a program that is not found.
        command: the command line.

    Returns:
        The finished process.

    Raises:
        FileNotFoundError: for 127.
        subprocess.CalledProcessError: for any other status but 0.
    """
    if status == NOT_FOUND:
        raise FileNotFoundError(command[0])
    if status:
        raise subprocess.CalledProcessError(status, command)
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
        "user": {"login": "author"},
        "body": "",
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


def run_git(directory: pathlib.Path, *arguments: str) -> str:
    """Run git for a test's setup, never signing (the machine's config may).

    Args:
        directory: where.
        *arguments: git's arguments.

    Returns:
        git's output.
    """
    done = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-C", str(directory), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout


def commit_file(checkout: pathlib.Path, name: str) -> None:
    """Add and commit one file.

    Args:
        checkout: the checkout.
        name: the file's name (and its content, and the commit message).
    """
    (checkout / name).write_text(name)
    run_git(checkout, "add", name)
    run_git(checkout, *IDENTITY, "commit", "-q", "-m", name)


def make_repository(workspace: pathlib.Path) -> pathlib.Path:
    """Make a bare ``origin`` with one commit on ``main``, and a clone of it.

    Args:
        workspace: where the clone goes, as ``project``.

    Returns:
        The clone.
    """
    seed = directory()
    run_git(seed, "init", "-q", "-b", "main")
    commit_file(seed, "README")
    origin = directory() / "origin.git"
    run_git(seed, "clone", "-q", "--bare", str(seed), str(origin))
    clone = workspace / "project"
    run_git(workspace, "clone", "-q", str(origin), str(clone))
    return clone


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


def directory() -> pathlib.Path:
    """A new temporary directory.

    Returns:
        Its path.
    """
    ceiling = os.path.realpath(tempfile.gettempdir())
    os.environ["GIT_CEILING_DIRECTORIES"] = ceiling  # no git repository above a test's
    return pathlib.Path(tempfile.mkdtemp())


def write(path: pathlib.Path, text: str) -> None:
    """Write a file, making its directory.

    Args:
        path: the file.
        text: its content.
    """
    os.makedirs(path.parent, exist_ok=True)
    path.write_text(text)


def push(checkout: pathlib.Path) -> None:
    """Push a checkout's branch to ``origin``.

    Args:
        checkout: the checkout.
    """
    run_git(checkout, "push", "-q", "origin", "HEAD")


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


def add_worktree(clone: pathlib.Path, name: str) -> pathlib.Path:
    """Add a worktree beside the clone, on a new branch.

    Args:
        clone: the main clone.
        name: the worktree's and the branch's name.

    Returns:
        The worktree.
    """
    path = clone.parent / name
    run_git(clone, "worktree", "add", "-q", str(path), "-b", name)
    return path


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
