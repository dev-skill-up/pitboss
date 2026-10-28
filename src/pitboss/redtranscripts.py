"""What the pushing worker ran locally, read from the subagent transcripts."""

import dataclasses
import json
import pathlib
from typing import Iterable, Mapping, Protocol, Sequence

SHORT_SHA = 7


class Transcripts(Protocol):
    """Where the workers' transcripts are read from."""

    def names(self) -> Sequence[str]:
        """List the agents that have a transcript.

        Returns:
            The agent ids.
        """

    def read(self, agent: str) -> str:
        """Read one agent's transcript (JSON lines).

        Args:
            agent: the agent id.

        Returns:
            Its text.
        """


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class DirectoryTranscripts:
    """Transcripts in files ``agent-<id>.jsonl`` found under a directory.

    The files are listed once, when it is made by ``directory``.
    """

    _paths: Mapping[str, pathlib.Path]

    def names(self) -> Sequence[str]:
        """List the agents that have a transcript.

        Returns:
            The agent ids.
        """
        return sorted(self._paths)

    def read(self, agent: str) -> str:
        """Read one agent's transcript.

        Args:
            agent: the agent id.

        Returns:
            Its text.
        """
        return self._paths[agent].read_text(encoding="utf-8", errors="replace")


def directory(root: pathlib.Path) -> Transcripts:
    """Transcripts in a directory.

    Args:
        root: the directory, searched recursively.

    Returns:
        The transcripts.
    """
    found = root.rglob("agent-*.jsonl")
    paths = {path.stem.removeprefix("agent-"): path for path in found}
    return DirectoryTranscripts(_paths=paths)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class LocalRuns:
    """What a push's worker ran before it.

    Attributes:
        agent: the agent whose transcript was found, else empty.
        found: whether a transcript was found for the push.
        commands: the shell commands it ran before the push, in order.
        ran: the failing names found among the commands.
        not_ran: the failing names not found among them.
        searched: how many transcripts were searched.
    """

    agent: str
    found: bool
    commands: Sequence[str]
    ran: Sequence[str]
    not_ran: Sequence[str]
    searched: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Searched:
    """The transcripts searched for a set of pushes.

    Attributes:
        pushes: for each push (branch, first seven digits of the commit) whose
            transcript was found, its agent and the commands before the push.
        count: how many transcripts there are.
    """

    pushes: Mapping[tuple[str, str], tuple[str, Sequence[str]]]
    count: int


def _commands(entries: Sequence[str]) -> Iterable[tuple[int, str]]:
    for index, entry in enumerate(entries):
        try:
            content = json.loads(entry)["message"]["content"]
        except (ValueError, KeyError, TypeError):
            continue
        for item in content if isinstance(content, list) else []:
            if isinstance(item, dict) and item.get("name") == "Bash":
                yield index, str(item.get("input", {}).get("command", ""))


def _before_push(entries: Sequence[str], short: str) -> Sequence[str]:
    mention = next(
        (i for i, entry in enumerate(entries) if short in entry), len(entries)
    )
    pairs = list(_commands(entries))
    push = next(
        (i for i, command in pairs if i >= mention and "git push" in command),
        len(entries),
    )
    return [command for i, command in pairs if i < push]


def search(source: Transcripts, pushes: Iterable[tuple[str, str]]) -> Searched:
    """Search the transcripts, once, for the pushes of commits.

    A transcript is a push's when it names both the branch and the commit (by
    its first seven digits). The search stops when every push has one, and
    never guesses: no match, no commands.

    Args:
        source: the transcripts.
        pushes: each push's branch and commit SHA.

    Returns:
        What was found.
    """
    wanted = {(branch, sha[:SHORT_SHA]) for branch, sha in pushes}
    found: dict[tuple[str, str], tuple[str, Sequence[str]]] = {}
    names = source.names()
    for agent in names:
        if len(found) == len(wanted):
            break
        text = source.read(agent)
        for branch, short in wanted - found.keys():
            if branch in text and short in text:
                commands = _before_push(text.splitlines(), short)
                found[(branch, short)] = (agent, commands)
    return Searched(pushes=found, count=len(names))


def local_runs(
    searched: Searched, branch: str, sha: str, names: Sequence[str]
) -> LocalRuns:
    """What the worker of a push ran before it, from what was searched.

    Args:
        searched: the search.
        branch: the pushed branch.
        sha: the pushed commit.
        names: the failing job, step and files, to look for in the commands.

    Returns:
        What was found.
    """
    agent, commands = searched.pushes.get((branch, sha[:SHORT_SHA]), ("", []))
    joined = "\n".join(commands).lower()
    ran = [name for name in names if name.lower() in joined]
    return LocalRuns(
        agent=agent,
        found=bool(agent),
        commands=commands,
        ran=ran,
        not_ran=[name for name in names if name not in ran],
        searched=searched.count,
    )
