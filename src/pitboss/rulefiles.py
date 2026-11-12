"""The brief's rule files: every file that binds a ticket's paths, closed world.

Pitboss#444.

The keyword is brief-rules. The writer takes the repository's ``CLAUDE.md`` and
``CLAUDE.local.md``, those of every directory on the way to a ticket path (and
under a ticket directory), ``.claude/agents/worker.md``, every rule file of
``.claude/rules/`` (recursively) whose ``paths:`` match a file of the ticket or
that has no front matter, and the user's ``~/.claude/CLAUDE.md``. A front matter
is read by lines and must be absent or exactly the keys of ``KEYS``, with
``paths:`` a block list; any other form refuses the brief, naming the file, so
nothing is dropped as "not applicable". ``gates_for`` names the verdict's gates on
the ticket's paths. ``rulecount`` counts the same files another way.
"""

import dataclasses
import hashlib
import pathlib
import re
from typing import Sequence

KEYS = frozenset({"paths", "description"})
NAMES = ("CLAUDE.md", "CLAUDE.local.md")
WORKER = ".claude/agents/worker.md"
RULES = ".claude/rules"
KEY = re.compile(r"(\w[\w-]*):(.*)")
GLOB = re.compile(r"\s+-\s+(\"[^\"]+\"|'[^']+'|[^\s'\"#][^#]*?)\s*")
PATH_GATES = (
    (
        r"^\.github/workflows/",
        (
            "a workflow file: text-lint must be green on the head (the body cites the"
            " scratch run) before arm or merge"
        ),
    ),
    (
        r"\.(md|rst)$",
        (
            "a .md or .rst file: lines are only removed; an added line stops undraft,"
            " arm and merge"
        ),
    ),
    (
        r"(^|/)CODEOWNERS$",
        "CODEOWNERS: stops arm and merge until a recorded override names it",
    ),
)
GATES = "GATES ON THESE PATHS"


class Refused(Exception):
    """A rule file is in no form the writer reads."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ticket:
    """Where a brief is written for.

    Attributes:
        checkout: the repository's checkout.
        paths: the ticket's paths, relative to the checkout.
        home: the user's home directory.
    """

    checkout: pathlib.Path
    paths: Sequence[str]
    home: pathlib.Path


def _glob_line(name: str, key: str, line: str, globs: list[str]) -> None:
    match = GLOB.fullmatch(line)
    if key == "paths" and match:
        globs.append(match.group(1).strip("'\""))
    elif not (key == "description" and line.startswith((" ", "\t"))):
        raise Refused(f"{name}: front matter line not in a known form: {line[:40]!r}")


def _key_line(name: str, match: re.Match[str]) -> str:
    key, rest = match.group(1), match.group(2).strip()
    if key not in KEYS:
        raise Refused(f"{name}: front matter key {key!r} has no row")
    if key == "paths" and rest:
        raise Refused(f"{name}: `paths:` is not a block list ({rest[:30]!r})")
    return key


def front(text: str, name: str) -> Sequence[str] | None:
    """The ``paths:`` globs of a rule file.

    Args:
        text: the file's text.
        name: its path, for the refusal.

    Returns:
        The globs, or None when it has no front matter (it applies to every path).

    Raises:
        Refused: the front matter is in no form the writer reads.
    """
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        raise Refused(f"{name}: front matter is not closed")
    globs: list[str] = []
    key, seen = "", False
    for line in text[4:end].split("\n"):
        if match := KEY.fullmatch(line):
            key = _key_line(name, match)
            seen = seen or key == "paths"
        elif line.strip():
            _glob_line(name, key, line, globs)
    if seen and not globs:
        raise Refused(f"{name}: `paths:` with no entry")
    return globs if seen else None


def _pattern(glob: str) -> re.Pattern[str]:
    escaped = re.escape(glob).replace(r"\*\*/", "(.*/)?").replace(r"\*\*", ".*")
    return re.compile(
        "^" + escaped.replace(r"\*", "[^/]*").replace(r"\?", "[^/]") + "$"
    )


def files_of(ticket: Ticket) -> Sequence[str]:
    """The files a ticket's paths name.

    Args:
        ticket: the ticket.

    Returns:
        Each file, relative to the checkout (a directory gives every file under it).
    """
    found: list[str] = []
    for each in ticket.paths:
        path = ticket.checkout / each
        if path.is_dir():
            found += [
                str(item.relative_to(ticket.checkout))
                for item in sorted(path.rglob("*"))
                if item.is_file() and ".git" not in item.parts
            ]
        else:
            found.append(each)
    return found


def _directories(ticket: Ticket, files: Sequence[str]) -> Sequence[str]:
    found = set()
    for each in [*files, *ticket.paths]:
        parts = pathlib.PurePosixPath(each).parts
        found |= {"/".join(parts[:index]) for index in range(1, len(parts))}
    for each in ticket.paths:
        if (ticket.checkout / each).is_dir():
            found |= {
                str(item.relative_to(ticket.checkout))
                for item in (ticket.checkout / each).rglob("*")
                if item.is_dir()
            }
            found.add(each.rstrip("/"))
    return sorted(found)


def _rules(ticket: Ticket, files: Sequence[str]) -> Sequence[pathlib.Path]:
    found = []
    for path in sorted((ticket.checkout / RULES).rglob("*.md")):
        globs = front(
            path.read_text(encoding="utf-8"), str(path.relative_to(ticket.checkout))
        )
        if globs is None or any(
            _pattern(glob).match(each) for glob in globs for each in files
        ):
            found.append(path)
    return found


def required(ticket: Ticket) -> Sequence[pathlib.Path]:
    """Every file that binds the ticket's paths.

    Args:
        ticket: the ticket.

    Returns:
        The files, in the order the brief carries them.
    """
    root, files = ticket.checkout, files_of(ticket)
    found = [root / name for name in (*NAMES, WORKER) if (root / name).is_file()]
    for directory in _directories(ticket, files):
        found += [
            root / directory / name
            for name in NAMES
            if (root / directory / name).is_file()
        ]
    found += _rules(ticket, files)
    user = ticket.home / ".claude" / "CLAUDE.md"
    return [*found, user] if user.is_file() else found


def carried(path: pathlib.Path, text: str) -> str:
    """How the brief carries one file.

    Args:
        path: the file.
        text: its text.

    Returns:
        Its header line with its sha256, and its text.
    """
    return (
        f"RULE FILE {path} sha256 {hashlib.sha256(text.encode()).hexdigest()}\n{text}"
    )


def gates_for(ticket: Ticket) -> Sequence[str]:
    """The verdict's gates on the ticket's paths.

    Args:
        ticket: the ticket.

    Returns:
        What each gate whose path matches says.
    """
    files = [*files_of(ticket), *ticket.paths]
    return [
        text
        for pattern, text in PATH_GATES
        if any(re.search(pattern, each) for each in files)
    ]


def write(ticket: Ticket) -> str:
    """The rule files and the path gates a worker's brief carries.

    Args:
        ticket: the ticket.

    Returns:
        The text.
    """
    parts = [
        carried(path, path.read_text(encoding="utf-8")) for path in required(ticket)
    ]
    gates = gates_for(ticket)
    listed = f"\n{GATES}\n" + "".join(f"- {each}\n" for each in gates) if gates else ""
    return "\n".join(parts) + listed
