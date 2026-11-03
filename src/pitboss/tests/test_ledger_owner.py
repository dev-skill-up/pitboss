"""``slots next``, ``free`` and ``set`` and ``sweep`` know the ledger's owner."""

import json
import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from . import world

COMMANDS: Sequence[Sequence[str]] = (
    ("next",),
    ("free", "tiny"),
    ("set", "tiny", "agent-1", "#9"),
)
FLAG = "ledger-owner = true\n"
REFUSAL = "not the orchestrator config: use "
UNRECORDED = REFUSAL + "the configuration with ledger-owner = true"
MISSING = "LEDGER MISSING"
FIRST_SWEEP_LINE = (
    "NOT THE ORCHESTRATOR CONFIG: the slots and NEXT lines of this sweep are"
    " not the orchestrator list: use "
)


def other_config(here: world.World) -> str:
    """Write a configuration like the world's that does not say it owns the ledger.

    Args:
        here: the world.

    Returns:
        Its path.
    """
    path = here.workspace / "other.toml"
    path.write_text(pathlib.Path(here.config).read_text().replace(FLAG, ""))
    return str(path)


def record(here: world.World, path: str) -> None:
    """Make the ledger record the configuration that created it.

    Args:
        here: the world.
        path: that configuration's path.
    """
    book = json.loads(here.ledger.read_text())
    here.ledger.write_text(json.dumps({**book, "config": path}))


def outcomes(
    here: world.World, path: str, commands: Sequence[Sequence[str]] = COMMANDS
) -> Sequence[tuple[object, str]]:
    """Run ``slots`` commands with a configuration.

    Args:
        here: the world.
        path: the configuration.
        commands: each command's action, then its words.

    Returns:
        Each one's exit code and last line on standard error.
    """
    results = [
        world.invoke(here, "slots", words[0], path, *words[1:]) for words in commands
    ]
    return [(each.code, (each.err.splitlines() or [""])[-1]) for each in results]


class TestSlots(unittest.TestCase):
    """The three commands that refill a slot."""

    def test_owner_by_flag(self) -> None:
        """A configuration that says ``ledger-owner = true`` runs all three."""
        here = world.make_world()
        codes = [code for code, _ in outcomes(here, here.config)]
        assert_that(codes, equal_to([0, 0, 0]))

    def test_owner_by_record(self) -> None:
        """A configuration whose path the ledger records runs all three."""
        here = world.make_world()
        path = other_config(here)
        record(here, path)
        codes = [code for code, _ in outcomes(here, path)]
        assert_that(codes, equal_to([0, 0, 0]))

    def test_record_is_kept(self) -> None:
        """A change to the ledger keeps the path it records."""
        here = world.make_world()
        record(here, here.config)
        outcomes(here, here.config, COMMANDS[2:])
        kept = json.loads(here.ledger.read_text())["config"]
        assert_that(kept, equal_to(here.config))

    def test_not_owner_recorded(self) -> None:
        """Another configuration exits 1, names the recorded one, changes nothing."""
        here = world.make_world()
        record(here, here.config)
        before = here.ledger.read_bytes()
        found = outcomes(here, other_config(here))
        assert_that(found, equal_to([(1, REFUSAL + here.config)] * 3))
        assert_that(
            (here.ledger.read_bytes(), here.ledger.with_suffix(".log").exists()),
            equal_to((before, False)),
        )

    def test_not_owner_unrecorded(self) -> None:
        """A ledger that records no path is owned only by a flagged configuration."""
        here = world.make_world()
        before = here.ledger.read_bytes()
        found = outcomes(here, other_config(here))
        assert_that(found, equal_to([(1, UNRECORDED)] * 3))
        assert_that(here.ledger.read_bytes(), equal_to(before))

    def test_not_owner_without_ledger(self) -> None:
        """With no ledger file there is no owner yet: the ledger is missing."""
        here = world.make_world()
        here.ledger.unlink()
        code, line = outcomes(here, other_config(here), COMMANDS[:1])[0]
        assert_that((code, line.startswith(MISSING)), equal_to((1, True)))

    def test_other_commands_are_not_checked(self) -> None:
        """``show`` still works from any configuration."""
        here = world.make_world()
        found = outcomes(here, other_config(here), (("show",),))
        assert_that([code for code, _ in found], equal_to([0]))


def sweep_first_line(here: world.World, path: str) -> str:
    """The first line a sweep prints.

    Args:
        here: the world.
        path: the configuration.

    Returns:
        The line.
    """
    return world.invoke(here, "sweep", path, "--now", world.FUTURE).out.splitlines()[0]


class TestSweep(unittest.TestCase):
    """The first line of a sweep."""

    def test_not_owner(self) -> None:
        """The first line says the lists are not the orchestrator's."""
        here = world.make_world()
        record(here, here.config)
        first = sweep_first_line(here, other_config(here))
        assert_that(first, equal_to(FIRST_SWEEP_LINE + here.config))

    def test_owner(self) -> None:
        """An owner's sweep has no such line."""
        here = world.make_world()
        first = sweep_first_line(here, here.config)
        assert_that(first.startswith("NOT THE ORCHESTRATOR"), equal_to(False))
