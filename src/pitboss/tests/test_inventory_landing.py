"""docs/quire-inventory-landing.py exits 1 on a MISSING row (pitboss#71)."""

import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from typing import Callable, Sequence

from hamcrest import assert_that, equal_to

ROOT = pathlib.Path(*pathlib.Path(__file__).resolve().parts[:-4])
SCRIPT = ROOT / "docs" / "quire-inventory-landing.py"
SKILL = pathlib.Path("plugins/pitboss/skills/sweep")
REFERENCES = SKILL / "references"
TICKET_RULE = "A ticket is one ticket and one PR; it is split only, and always,"
BLOCKED_RULE = "A blocked ticket"
CI_HEADING = "## CI is pinned"
FLAGGED = ("MISSING", "STAYS-IN-QUIRE")
TICKET_ROW = "MISSING orchestration.md Tickets one ticket, one PR, split only when "
BLOCKED_ROW = "MISSING orchestration.md Tickets blocked is not started"
SLOTS_ROWS = [
    "MISSING worker.md not-done form",
    "MISSING qsweep order of the next item",
    "MISSING slots set and free (split)",
    "MISSING slots check",
    "MISSING slots check before you answer",
]

Planter = Callable[[pathlib.Path], None]


def replacing(name: str, *edits: tuple[str, str]) -> Planter:
    """A change of a reference file: each old text replaced by its new.

    Args:
        name: the file of the references.
        *edits: pairs of the text to find and the text to put there.

    Returns:
        A function that makes the change in a tree.
    """

    def plant(tree: pathlib.Path) -> None:
        target = tree / REFERENCES / name
        text = target.read_text()
        for old, new in edits:
            text = text.replace(old, new)
        target.write_text(text)

    return plant


def removing(name: str) -> Planter:
    """The removal of a reference file.

    Args:
        name: the file of the references.

    Returns:
        A function that removes it from a tree.
    """
    return lambda tree: (tree / REFERENCES / name).unlink()


def flagged_run(*arguments: str) -> tuple[int, Sequence[str]]:
    """The exit status and the failure lines of the script.

    Args:
        *arguments: the arguments after the script's name.

    Returns:
        The status, and each output line that starts with a failure word.
    """
    run = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    return run.returncode, [x for x in run.stdout.splitlines() if x.startswith(FLAGGED)]


def planted(plant: Planter) -> tuple[int, Sequence[str]]:
    """The script on a copy of the skill's files that has been changed.

    Args:
        plant: the change made to the copy.

    Returns:
        The status and the failure lines, as ``flagged_run`` gives them.
    """
    with tempfile.TemporaryDirectory() as directory:
        tree = pathlib.Path(directory)
        shutil.copytree(ROOT / SKILL, tree / SKILL)
        plant(tree)
        return flagged_run(str(tree))


class TestLanding(unittest.TestCase):
    """The script's exit status."""

    def test_this_repository_lands_every_row(self) -> None:
        """The tree itself has no MISSING row and the script exits 0."""
        assert_that(flagged_run(), equal_to((0, [])))

    def test_planted_failures_exit_one(self) -> None:
        """A missing phrase, two, a missing file and quire text are exit 1."""
        two = replacing("rules.md", (TICKET_RULE, "x"), (BLOCKED_RULE, "y"))
        quire = replacing("ci.md", (CI_HEADING, "Dependabot\n" + CI_HEADING))
        cases = [
            (replacing("rules.md", (TICKET_RULE, "x")), 1, ["MISSING"]),
            (two, 2, ["MISSING"]),
            (removing("slots.md"), len(SLOTS_ROWS), ["MISSING"]),
            (quire, 1, ["STAYS-IN-QUIRE"]),
        ]
        found = []
        for plant, count, words in cases:
            status, lines = planted(plant)
            found.append((status, len(lines), {x.split()[0] for x in lines}))
        expected = [(1, count, set(words)) for _, count, words in cases]
        assert_that(found, equal_to(expected))

    def test_planted_rows_are_named(self) -> None:
        """The rows a change breaks are exactly the ones named in the output."""
        two = replacing("rules.md", (TICKET_RULE, "x"), (BLOCKED_RULE, "y"))
        _, ticket_lines = planted(two)
        _, slots_lines = planted(removing("slots.md"))
        assert_that(len(ticket_lines), equal_to(2))
        assert_that(ticket_lines[0].startswith(TICKET_ROW), equal_to(True))
        assert_that(ticket_lines[1], equal_to(BLOCKED_ROW))
        assert_that(list(slots_lines), equal_to(SLOTS_ROWS))
