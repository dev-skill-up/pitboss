"""Each seed the Done-when of #524 names is refused by exactly one named rule."""

import pathlib
import unittest
from typing import Mapping

from hamcrest import assert_that, contains_exactly, equal_to

from .. import onepathproofs, proofseeds, proofsource
from . import test_capability_seeds

ROOT = pathlib.Path(proofseeds.__file__).resolve().parents[2]
TEXTS = proofsource.read(ROOT)

# the seeds the Done-when names, each with the rule that refuses it: a rule of the
# capability checker (``test_capability_seeds``), a proof of the one path
# (``onepathproofs``) or, for a re-pointed ticket, the flow's row for it
PROOFS: Mapping[str, str] = {
    "a step its own command refuses": "P8.4",
    "an Idle without an event": "P12.1",
    "an accepted hand-back without all checks": "P12.3",
    "an escalate-to-the-owner ruling": "R1.1",
    "a hand-back store written and read at different paths": "P12.2",
    "a version-skewed act": "P12.4",
}
CHECKER: Mapping[str, str] = {
    "a read outside the capability": "a read of a file by its path",
    "a second read of one input": "a second read of one input",
    "a runtime string that names a Step": "a Step named by a string read at run time",
    "a TYPE_CHECKING-else read": "code that runs only when mypy does not read it",
    "a Protocol-injected reader": "a reader handed to the decision as a Protocol",
}


def _found_by(bullet: str) -> set[str]:
    seeded = proofseeds.seeded(TEXTS, onepathproofs.CASES[bullet].seed)
    package = proofsource.of_texts(seeded)
    return {name for name, case in onepathproofs.CASES.items() if case.proof(package)}


class TestDoneWhenSeeds(unittest.TestCase):
    """The proofs refuse their seed, each alone; the checker's seeds are named."""

    def test_each_proof_seed_is_refused_by_its_one_rule(self) -> None:
        """Seeding one proof's edit breaks that proof and no other."""
        for name, bullet in PROOFS.items():
            with self.subTest(name):
                assert_that(sorted(_found_by(bullet)), contains_exactly(bullet))

    def test_each_checker_seed_is_one_of_the_checkers(self) -> None:
        """The seeds the checker is tested with name each of these."""
        names = {each.name for each in test_capability_seeds.SEEDS}
        assert_that(set(CHECKER.values()) <= names, equal_to(True))
