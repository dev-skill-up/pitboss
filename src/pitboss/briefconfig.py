"""What a project's briefs say beyond the process (keyword: brief, pitboss#118)."""

import dataclasses
from typing import AbstractSet, Mapping, Sequence


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Brief:
    """The ``[slots.brief]`` table.

    Attributes:
        drafts: whether a PR starts as a draft; false opens it ready.
        holds: whether pushes to a PR wait for the runners (``pitboss push``);
            false pushes with ``git push``.
        worker_lines: facts of the project every worker brief states (for
            example the path of the compiler).
        review_lines: facts of the project every review brief states.
        no_drafts: the repositories whose PRs open ready whatever ``drafts``
            says, as the file names them (``configfile.load_brief`` completes
            them; keyword: pitboss-exempt, pitboss#113).
        flake_worker_lines: lines a worker brief adds for a p0 ticket about a
            failing test, before ``worker_lines`` (keyword: flake, pitboss#278).
        flake_review_lines: lines a review brief adds for a PR that fixes such
            a ticket, before ``review_lines``.
        quarantine_globs: the files whose tests such a ticket may mark
            ``.fixme``; ``pitboss next TICKET`` prints an ``NOT QUARANTINED`` line when
            none cites the ticket.
    """

    drafts: bool
    holds: bool
    worker_lines: Sequence[str]
    review_lines: Sequence[str]
    no_drafts: AbstractSet[str] = frozenset()
    flake_worker_lines: Sequence[str] = ()
    flake_review_lines: Sequence[str] = ()
    quarantine_globs: Sequence[str] = ()


def _flag(table: Mapping[str, object], key: str) -> bool:
    found = table.get(key, True)
    if isinstance(found, bool):
        return found
    raise ValueError(f"[slots.brief] {key} must be true or false, not {found!r}")


def _lines(table: Mapping[str, object], key: str) -> Sequence[str]:
    found = table.get(key, [])
    if not isinstance(found, list):
        raise ValueError(f"[slots.brief] {key} must be a list of lines, not {found!r}")
    return tuple(str(each) for each in found)


def _brief_table(document: Mapping[str, object]) -> Mapping[str, object]:
    match document.get("slots", {}):
        case {"brief": dict() as table}:
            return table
        case {"brief": other}:
            raise ValueError(f"[slots.brief] must be a table, not {other!r}")
        case {}:
            return {}
        case other:
            raise ValueError(f"[slots] must be a table, not {other!r}")


def from_document(document: Mapping[str, object]) -> Brief:
    """Read the ``[slots.brief]`` table.

    Args:
        document: the parsed configuration.

    Returns:
        The settings; drafts and holds are on unless turned off, and the
        lines are none when the table is absent. A value of the wrong type
        is a ``ValueError`` that names the key.
    """
    table = _brief_table(document)
    return Brief(
        drafts=_flag(table, "drafts"),
        holds=_flag(table, "holds"),
        worker_lines=_lines(table, "worker_lines"),
        review_lines=_lines(table, "review_lines"),
        no_drafts=frozenset(_lines(table, "no_drafts")),
        flake_worker_lines=_lines(table, "flake_worker_lines"),
        flake_review_lines=_lines(table, "flake_review_lines"),
        quarantine_globs=_lines(table, "quarantine_globs"),
    )
