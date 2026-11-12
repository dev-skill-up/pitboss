"""I36 of pitboss#444: every running agent counts toward the cap."""

import unittest

from hamcrest import assert_that, equal_to

from . import world
from .cleanworld import same
from .says import says
from .test_slot_commands import run_all

WORKER = ("set", "tiny", "worker", "#9", "--running", "worker")
DIAGNOSE = (
    "set",
    "tiny",
    "doctor",
    "#9",
    "--kind",
    "diagnose",
    "--running",
    "worker",
    "doctor",
)


class TestCap(unittest.TestCase):
    """A diagnosis takes a slot like a worker."""

    def test_i36_a_diagnosis_is_refused_while_a_worker_holds_the_slot(self) -> None:
        """The refusal names the holder, its kind, ticket, time and the next slot."""
        done = run_all(world.make_world(), [WORKER, DIAGNOSE])[1]
        said = ["worker (start, owner/project#9, since", "the next free slot takes"]
        assert_that(
            (done.code, [w in done.err for w in said]), equal_to((2, [True] * 2))
        )

    def test_i36_the_freed_slot_takes_the_diagnosis(self) -> None:
        """The same call after the worker handed back is accepted and recorded."""
        here = world.make_world()
        freed = ("free", "tiny", "--done", "worker")
        done = run_all(here, [WORKER, freed, DIAGNOSE])[2]
        taken = '"diagnose"' in here.ledger.read_text()
        assert_that((done.code, taken), equal_to((0, True)))

    def test_i36_an_agent_the_ledger_lacks_fills_the_cap(self) -> None:
        """Two running agents that no slot records fill the two empty slots."""
        extra = (
            "set",
            "tiny",
            "doctor",
            "#9",
            "--running",
            "doctor",
            "ghost-1",
            "ghost-2",
        )
        done = run_all(world.make_world(), [extra])[0]
        says(done.err, "ghost-1")
        same(done.code, 2)
