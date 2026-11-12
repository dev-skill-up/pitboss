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
import enum
import re
from typing import Callable, Mapping, MutableSequence, Sequence

NAMES = ("CLAUDE.md", "CLAUDE.local.md")
WORKER = ".claude/agents/worker.md"
RULES = ".claude/rules"
KEY_LINE = re.compile(r"(\w[\w-]*):(.*)")
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


class Key(enum.Enum):
    """A key of a rule file's front matter.

    Attributes:
        PATHS: the globs of the files the rule binds.
        DESCRIPTION: what the rule is about.
    """

    PATHS = enum.auto()
    DESCRIPTION = enum.auto()


KEYS = {each.name.lower(): each for each in Key}


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


def _refused(name: str, line: str) -> Refused:
    return Refused(f"{name}: front matter line not in a known form: {line[:40]!r}")


def _path_line(name: str, line: str, globs: MutableSequence[str]) -> None:
    match = GLOB.fullmatch(line)
    if not match:
        raise _refused(name, line)
    globs.append(match.group(1).strip("'\""))


def _description_line(name: str, line: str, globs: MutableSequence[str]) -> None:
    # a description continues on indented lines; it adds no glob
    if not line.startswith((" ", "\t")):
        raise _refused(name, line)


def _keyless_line(name: str, line: str, globs: MutableSequence[str]) -> None:
    raise _refused(name, line)


LINES: Mapping[Key | None, Callable[[str, str, MutableSequence[str]], None]] = {
    Key.PATHS: _path_line,
    Key.DESCRIPTION: _description_line,
    None: _keyless_line,
}


def _key_line(name: str, match: re.Match[str]) -> Key:
    word, rest = match.group(1), match.group(2).strip()
    if word not in KEYS:
        raise Refused(f"{name}: front matter key {word!r} has no row")
    if KEYS[word] is Key.PATHS and rest:
        raise Refused(f"{name}: `paths:` is not a block list ({rest[:30]!r})")
    return KEYS[word]


def _read_lines(name: str, matter: str, globs: MutableSequence[str]) -> bool:
    # adds the globs of the front matter's lines; whether it has a `paths:` key
    key: Key | None = None
    seen = False
    for line in matter.split("\n"):
        if match := KEY_LINE.fullmatch(line):
            key = _key_line(name, match)
            seen = seen or key is Key.PATHS
        elif line.strip():
            LINES[key](name, line, globs)
    return seen


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
    seen = _read_lines(name, text[4:end], globs)
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
                _relative(ticket, item)
                for item in sorted(path.rglob("*"))
                if item.is_file() and ".git" not in item.parts
            ]
        else:
            found.append(each)
    return found


def _relative(ticket: Ticket, item: pathlib.Path) -> str:
    # a file's path in the checkout
    return str(item.relative_to(ticket.checkout))


def _directories(ticket: Ticket, files: Sequence[str]) -> Sequence[str]:
    found = set()
    for each in [*files, *ticket.paths]:
        parts = pathlib.PurePosixPath(each).parts
        found |= {"/".join(parts[:index]) for index in range(1, len(parts))}
    for each in ticket.paths:
        if (ticket.checkout / each).is_dir():
            found |= {
                _relative(ticket, item)
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
    return f"RULE FILE {path} {quoted(text)}"


def quoted(text: str) -> str:
    """A text as a brief holds it: its sha256 line, then the text.

    Args:
        text: the text.

    Returns:
        ``sha256 <digest>``, a newline, and the text.
    """
    return f"sha256 {hashlib.sha256(text.encode()).hexdigest()}\n{text}"


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
