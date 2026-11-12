"""The gates a changed file has, and the Plan row each needs (keyword: file-gates).

quire#1120 edited ``relock.yml``, which runs from the default branch, so text-lint's
scratch-run gate wanted the body to cite a run of bats-lang/relock-scratch; the
worker brief never named it and the Plan had no row for it. ``filegates.tsv`` is
the table: a path (and, where the rule is about content, the lines the diff adds or
the file at the head), the Plan row that meets the gate, and the sentence of the
repository's CLAUDE.md it is made from. The worker brief lists the gates of the
files the ticket names; ``plan-check`` refuses a Plan with no row for a gate the
diff has. It shares ``reporules`` (the diff reader and the CLAUDE.md).
"""

import dataclasses
import re
from typing import Callable, Sequence

from . import briefconfig, ghapi, phrases, reporules

CHECK = "file-gate"
NONE = "-"
FIELDS = 8
PATH = re.compile(
    r"[\w.-]+(?:/[\w.*-]+)*(?:\.(?:ya?ml|bats|toml|lock)|/c)\b|\.github/[\w./-]+"
)
Read = Callable[[str], str | None]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Gate:
    """A gate of the table.

    Attributes:
        id: its name.
        scope: ``owner:OWNER`` or ``claude:TEXT``.
        paths: a pattern over the changed path.
        added: a pattern over the lines added to it, ``-`` for none.
        content: a pattern over the file at the head, ``-`` for none.
        needle: a pattern the Plan row that meets the gate holds.
        form: the row, in words.
        source: ``REPOSITORY/FILE: sentence`` it is made from.
    """

    id: str
    scope: str
    paths: str
    added: str
    content: str
    needle: str
    form: str
    source: str


def parse(text: str) -> Sequence[Gate]:
    """The gates of a table.

    Args:
        text: the file; ``#`` lines and blank lines are skipped.

    Returns:
        The gates (a row with a wrong number of fields is a ``ValueError``).
    """
    rows = [each.split("\t") for each in text.splitlines() if each.strip()]
    rows = [each for each in rows if not each[0].startswith("#")]
    for each in rows:
        if len(each) != FIELDS:
            raise ValueError(f"filegates.tsv: {each[0]} has {len(each)} fields")
    return [Gate(**dict(zip(Gate.__dataclass_fields__, each))) for each in rows]


def shipped() -> Sequence[Gate]:
    """The gates of the shipped table.

    Returns:
        The gates.
    """
    return parse(phrases.shipped_text("filegates.tsv"))


def _in_scope(gate: Gate, slug: str, claude: str) -> bool:
    kind, _, value = gate.scope.partition(":")
    if kind == "owner":
        return slug.partition("/")[0] == value
    return value in claude


def _matches(pattern: str, text: str | None) -> bool:
    return pattern == NONE or (
        text is not None and re.search(pattern, text) is not None
    )


def applies(gate: Gate, path: str, added: Sequence[str], read: Read) -> bool:
    """Whether a changed file has a gate.

    Args:
        gate: the gate.
        path: the changed path.
        added: the lines the diff adds to it.
        read: reads a file of the head.

    Returns:
        True when the path, the added lines and the file's content all match.
    """
    return (
        re.search(gate.paths, path) is not None
        and _matches(gate.added, "\n".join(added))
        and _matches(gate.content, read(path))
    )


def of_diff(
    slug: str, diff: str, claude: str, read: Read
) -> Sequence[tuple[Gate, str]]:
    """The gates a diff has, each with the first path that has it.

    Args:
        slug: the repository, ``owner/name``.
        diff: the unified diff.
        claude: the repository's CLAUDE.md.
        read: reads a file of the head.

    Returns:
        ``(gate, path)`` for each gate of the table that is in scope and that a
        changed file has.
    """
    changed = reporules.added_lines(diff)
    return [
        (gate, path)
        for gate in shipped()
        if _in_scope(gate, slug, claude)
        for path in [
            each for each, _, lines in changed if applies(gate, each, lines, read)
        ][:1]
    ]


def finding(gate: Gate, path: str) -> str:
    """The finding of a gate with no row.

    Args:
        gate: the gate.
        path: a changed path that has it.

    Returns:
        The finding: the gate, the path, the row form and the source sentence.
    """
    return (
        f"{CHECK}: `{path}` has the gate {gate.id}: the Plan needs "
        f"{gate.form} ({gate.source})"
    )


def findings(
    slug: str, diff: str, section: str, files: tuple[str, Read]
) -> Sequence[str]:
    """What the Plan lacks for the gates of the files the diff changes.

    Args:
        slug: the repository, ``owner/name``.
        diff: the unified diff.
        section: the Plan section of the body.
        files: the repository's CLAUDE.md and a reader of the head's files.

    Returns:
        A finding for each gate that applies and whose needle the Plan does not
        hold.
    """
    claude, read = files
    return [
        finding(gate, path)
        for gate, path in of_diff(slug, diff, claude, read)
        if re.search(gate.needle, section, re.IGNORECASE) is None
    ]


def named(text: str) -> Sequence[str]:
    """The paths a ticket's text names.

    Args:
        text: the ticket (its Done-when).

    Returns:
        Each path-looking word, once.
    """
    return list(dict.fromkeys(each.group(0) for each in PATH.finditer(text)))


def _named_path(gate: Gate, path: str) -> bool:
    # a ticket says `relock.yml` for `.github/workflows/relock.yml`
    workflow = f".github/workflows/{path}" if "/" not in path else path
    return any(re.search(gate.paths, each) for each in (path, workflow))


def lines(slug: str, claude: str, ticket: str) -> Sequence[str]:
    """The lines a worker brief adds for the gates of the files a ticket names.

    Args:
        slug: the repository.
        claude: its CLAUDE.md.
        ticket: the ticket's text.

    Returns:
        Nothing when no named path has a gate; else the header and a line for
        each gate: the path, the row form and the source. A gate that also asks
        about the content or the added lines is said to apply when they match.
    """
    found = [
        f"    - `{path}`: gate {gate.id}: the Plan needs"
        f" {gate.form}{'' if gate.added == NONE and gate.content == NONE else ' (when the change matches)'}"
        f" ({gate.source})"
        for gate in shipped()
        if _in_scope(gate, slug, claude)
        for path in named(ticket)
        if _named_path(gate, path)
    ]
    head = (
        "FILE GATES (keyword: file-gates; `plan-check` refuses a Plan with no row for"
        " a gate that applies to a file the diff changes):"
    )
    return [head, *found] if found else []


def added(
    github: ghapi.GitHub, slug: str, ticket: str, project: briefconfig.Brief
) -> briefconfig.Brief:
    """The project's briefs with the repository's rules and the ticket's file gates.

    Args:
        github: the API.
        slug: the repository.
        ticket: the ticket's text.
        project: what the project's briefs say.

    Returns:
        The same, its review lines followed by the repository's rules
        (``reporules``) and its worker lines by ``lines`` of the CLAUDE.md.
    """
    claude = reporules.read(github, slug)
    more = lines(slug, claude, ticket)
    return dataclasses.replace(
        project,
        review_lines=[*project.review_lines, *reporules.lines(claude)],
        worker_lines=[*project.worker_lines, *more],
    )
