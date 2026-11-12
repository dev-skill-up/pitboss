"""The total verdict: the frozen enumeration, its cells.

Its pairs and every write's verb (pitboss#444).
"""

import collections
import functools
import hashlib
import pathlib
import unittest

from hamcrest import assert_that, equal_to

from .. import actverbs, enumeration, totaljson, totalroutes, totalverdict
from . import (
    coverwrites,
    scratch,
    totalcells,
    totalcomplete,
    totalpairs,
    totalworld,
    world,
)
from .fakes import write

SOURCE = pathlib.Path(__file__).parent.parent
SHA256 = {
    enumeration.VARIABLES: (
        "2967d3849c60b31278234ebc5f43967534efd4434fdc906b0225c701ee701dbc"
    ),
    enumeration.ACTIONS: (
        "c4f777245a4492773e9774b4acd2391b6d8c938125d1d9ec2442735785c65d82"
    ),
}


def _verdict(
    action: str, pull: totaljson.JsonMap, ctx: totaljson.JsonMap
) -> totalverdict.Answer:
    return totalverdict.verdict(action, pull, ctx, _policy())


@functools.cache
def _policy() -> totalverdict.Policy:
    return totalverdict.shipped_policy()


@functools.cache
def _pairs() -> totalpairs.Pairs:
    return totalpairs.run(totalworld.base(), totalcomplete.base_cells(), _verdict)


class TestFrozen(unittest.TestCase):
    """The frozen enumeration is what its sources give, byte for byte."""

    def test_444_the_frozen_sets_are_derived_from_their_sources(self) -> None:
        """Both files are written again from the sources and equal the shipped bytes."""
        derived = enumeration.derive()
        assert_that(
            derived,
            equal_to(
                (
                    enumeration.shipped(enumeration.VARIABLES),
                    enumeration.shipped(enumeration.ACTIONS),
                )
            ),
        )

    def test_444_the_hashes_reproduce(self) -> None:
        """The sha256 and the row count of each file are the plan's."""
        for name, digest in SHA256.items():
            text = enumeration.shipped(name)
            assert_that(
                hashlib.sha256(text.encode("utf-8")).hexdigest(), equal_to(digest)
            )
        counts = (
            len(enumeration.frozen(enumeration.VARIABLES)),
            len(enumeration.frozen(enumeration.ACTIONS)),
        )
        assert_that(counts, equal_to((188, 322)))


class TestCells(unittest.TestCase):
    """Every value of every variable, for each action, against the GO world."""

    def test_444_732_cells_with_0_uncovered(self) -> None:
        """526 fire on their own row, 206 are benign by a named reason.

        None is uncovered.
        """
        found = totalcells.tally(totalcomplete.base_cells(), _verdict)
        assert_that(
            (len(totalcomplete.base_cells()), dict(found)),
            equal_to((732, {totalcells.FIRES: 526, totalcells.BENIGN: 206})),
        )

    def test_444_every_stop_line_has_a_route(self) -> None:
        """No line the cells give is without a route."""
        lines = sorted(
            {
                line
                for cell in totalcomplete.base_cells()
                for line in _verdict(cell.action, cell.world.pull, cell.world.ctx).lines
            }
        )
        assert_that((totalpairs.routed(lines), len(lines) > 200), equal_to(([], True)))


class TestPairs(unittest.TestCase):
    """Every two cells together: the verdict answers, and never raises."""

    def test_444_a_wrong_answer_is_counted(self) -> None:
        """A stop line with no route is an exception of the pair."""
        unrouted = totalverdict.Answer(
            word=totalverdict.STOP, lines=["zzz: a line no route takes"]
        )
        found = totalpairs.run(
            totalworld.base(),
            totalcomplete.base_cells()[::100],
            lambda action, pull, ctx: unrouted,
        )
        assert_that(found.counts["exception"] > 0, equal_to(True))

    def test_444_equal_sets_are_no_change_whatever_the_hash_seed(self) -> None:
        """A set is compared by its members, not by the order it prints in."""
        names = [f"login{number}" for number in range(40)]
        origin = totalworld.World(pull={}, ctx={"authors": set(names)})
        again = totalworld.World(pull={}, ctx={"authors": set(reversed(names))})
        assert_that(totalpairs.change_of(origin, again), equal_to({}))

    def test_444_74991_pairs_with_0_exceptions(self) -> None:
        """GO and STOP add to the pairs, and no pair raised."""
        found = _pairs()
        assert_that(
            (found.counts["GO"] + found.counts["STOP"], list(found.exceptions)),
            equal_to((74991, [])),
        )


class TestCover(unittest.TestCase):
    """Every GitHub write has an act verb."""

    def test_444_cover_writes_at_0_uncovered(self) -> None:
        """Each write tool is read, a verb, or never used."""
        kinds = collections.Counter(
            row.kind for row in coverwrites.tools(actverbs.VERBS)
        )
        assert_that(dict(kinds), equal_to({"read": 24, "verb": 12, "unused": 12}))

    def test_444_cover_commands_at_0_uncovered(self) -> None:
        """38 commands: 11 write through a verb, 27 write nothing."""
        names = [
            name
            for name in enumeration.values("pitboss-command")
            if name != "mutation-check"
        ]
        kinds = collections.Counter(
            row.kind for row in coverwrites.commands(SOURCE, names, actverbs.VERBS)
        )
        assert_that(
            (len(names), dict(kinds)), equal_to((38, {"fires": 11, "benign": 27}))
        )

    def test_444_the_registered_commands_are_the_frozen_list_less_mutation_check(
        self,
    ) -> None:
        """mutation-check left the command list; nothing else came or went."""
        names = {
            name
            for name in enumeration.values("pitboss-command")
            if name != "mutation-check"
        }
        assert_that(set(coverwrites.call_graph(SOURCE).registered), equal_to(names))

    def test_444_a_tool_used_with_no_verb_is_uncovered(self) -> None:
        """With no verbs, a write tool the agents used is UNCOVERED."""
        kinds = {row.kind for row in coverwrites.tools({})}
        assert_that("UNCOVERED" in kinds, equal_to(True))

    def test_444_the_graph_reads_store_of_and_only_name_keywords(self) -> None:
        """A bare ``store_of`` is a write.

        A decorator keyword other than ``name`` registers nothing.
        """
        source = scratch.directory()
        write(
            source / "planted.py",
            "@register(help='x', name='planted')\ndef planted():\n    return"
            " store_of()\n\n@register(help='y')\ndef other():\n    return 1\n",
        )
        found = coverwrites.call_graph(source)
        assert_that(
            (dict(found.registered), found.writers),
            equal_to(({"planted": ("planted", "planted")}, {("planted", "planted")})),
        )

    def test_444_a_write_with_no_route_is_uncovered(self) -> None:
        """A command that writes and has no verb, and one that is not registered.

        Are each UNCOVERED.
        """
        found = coverwrites.commands(SOURCE, ["sweep", "no-such-command"], {})
        assert_that([row.kind for row in found], equal_to(["UNCOVERED", "UNCOVERED"]))


class TestInstructions(unittest.TestCase):
    """The sweep carries what each actor writes."""

    def test_444_the_sweep_prints_the_instructions(self) -> None:
        """The text of ``instructions()``, whole."""
        here = world.make_world()
        done = world.again(here, "sweep", f"--now={world.FUTURE}")
        assert_that(totalroutes.instructions() in done.out, equal_to(True))
