"""A head ``pitboss nox`` already ran green is not run again (keyword: nox-green, pitboss#345).

The owner's rule: ``pitboss nox`` runs before each push and when feedback is
needed, not again on a head it already passed. A passing run on a clean tree
writes ``pitboss-nox-green`` in the repository's git directory, with the head and
the time; a later run on the same clean head prints ``NOTE`` and exits 0 without
running unless ``--force`` is given. A dirty tree is never recorded or skipped:
it is not a head. Git and the clock are injected, so the tests run no real git.
"""

import dataclasses
import pathlib

from .noxcheck import Runner

RECORD = "pitboss-nox-green"
HEAD = ["git", "rev-parse", "HEAD"]
DIRECTORY = ["git", "rev-parse", "--absolute-git-dir"]
STATUS = ["git", "status", "--porcelain"]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Place:
    """Where a clean head's green run is recorded.

    Attributes:
        head: the head commit.
        path: the file that records the green run.
    """

    head: str
    path: pathlib.Path


def note_of(when: str) -> str:
    """The line printed for a head that already ran green.

    Args:
        when: the time of the green run.

    Returns:
        The line.
    """
    return (
        f"NOTE: this head already ran green at {when}; rerun only when feedback"
        " is needed (--force runs it again)"
    )


def place_of(run: Runner) -> Place | None:
    """The record of the clean head of the repository the command runs in.

    Args:
        run: runs a command line (git).

    Returns:
        The head and its record file; none when git cannot say, or when the
        tree has a change (a head is only a clean tree).
    """
    head, directory, status = run(HEAD), run(DIRECTORY), run(STATUS)
    if head.status or directory.status or status.status or status.output.strip():
        return None
    return Place(
        head=head.output.strip(),
        path=pathlib.Path(directory.output.strip()) / RECORD,
    )


def green_at(place: Place) -> str:
    """The time a head ran green.

    Args:
        place: the head and its record file.

    Returns:
        The time recorded for the head; empty when the record is missing,
        unreadable or for another head.
    """
    try:
        head, _, when = place.path.read_text(encoding="utf-8").strip().partition(" ")
    except (OSError, UnicodeError):
        return ""
    return when if head == place.head else ""


def record(place: Place, when: str) -> None:
    """Record that a head ran green.

    Args:
        place: the head and its record file.
        when: the time.
    """
    try:
        place.path.write_text(f"{place.head} {when}\n", encoding="utf-8")
    except OSError:  # pragma: no cover
        return
