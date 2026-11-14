"""The proofs of the one path, P1 to P11, on the package and its seeds (plan 6.3)."""

import argparse
import contextlib
import io
import pathlib
import re
import tempfile
import unittest
from typing import Mapping

from gather import commands as gather_commands
from gather.api import Wrapper
from hamcrest import assert_that, contains_string, equal_to, has_item

from .. import (
    cli_parser,
    config,
    decideproofs,
    mode,
    modeproof,
    pathproofs,
    proofseeds,
    proofsource,
)

# the repository: src/pitboss/pathproofs.py is two levels below it
ROOT = pathlib.Path(pathproofs.__file__).resolve().parents[2]
EMPTY = proofsource.of_texts({})
TICKET = gather_commands.add_argument("ticket", nargs="?")
NEXT_ONLY = {"next": [Wrapper(original=print, extra=(TICKET,))]}
TEXTS = proofsource.read(ROOT)
GUARDED = """

def _guarded(given: object) -> None:
    match given:
        case world.Stopped() if not given:
            pass
        case _ if not given:
            pass
"""


def _edited(path: str, old: str, new: str) -> proofsource.Package:
    # the package with one file's text changed; a text not there once is a failure
    seed = proofseeds.Seed(path=path, old=old, new=new)
    texts = proofseeds.seeded(TEXTS, seed)
    assert_that(texts != TEXTS, equal_to(True), f"{path}: {old!r} is not once")
    return proofsource.of_texts(texts)


def _path_of(name: str) -> str:
    # a module's file, as ``proofsource.read`` names it
    return f"src/{name.replace('.', '/')}.py"


def _bare_root(base: str) -> pathlib.Path:
    # a repository whose package has no module
    (pathlib.Path(base) / "src" / "pitboss").mkdir(parents=True)
    return pathlib.Path(base)


def _status_of_seeds(root: pathlib.Path) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return proofseeds.main(root, NEXT_ONLY)


def _status_of_main(root: pathlib.Path) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return pathproofs.main(root)


def _exits(
    args: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
) -> mode.Mode:
    raise SystemExit(2)


def _no_mode(
    args: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
) -> mode.Mode:
    return mode.Next()


def _not_a_mode(
    args: argparse.Namespace, project: config.Repo, options: Mapping[str, str]
) -> mode.Mode:
    return config.Repo(owner="o", name="n", slug="o/n")  # type: ignore[return-value]


class TestThePackage(unittest.TestCase):
    """Plan 6.3 and 6.5: the proofs hold on the package and find each seed."""

    def test_every_proof_holds_and_every_seed_is_found(self) -> None:
        """P1 to P11 hold, and each fails on its one seeded edit."""
        missed = proofseeds.missed(TEXTS, cli_parser.table(), proofseeds.other_modes)
        assert_that(missed, equal_to([]))

    def test_the_path_proofs_exit_zero_on_the_package(self) -> None:
        """``python -m pitboss.pathproofs`` exits 0 at the repository's root."""
        assert_that(_status_of_main(ROOT), equal_to(0))

    def test_p4_exits_zero_on_the_package(self) -> None:
        """``python -m pitboss.modeproof`` exits 0 at the repository's root."""
        with contextlib.redirect_stdout(io.StringIO()):
            status = modeproof.main(ROOT, mode.parse)
        assert_that(status, equal_to(0))


class TestNoPackage(unittest.TestCase):
    """Plan 6.3: a module a proof requires that is gone is a finding."""

    def test_the_proofs_name_what_is_missing(self) -> None:
        """P1, P8 and P11 each say the function they read is not there."""
        found = pathproofs.findings(EMPTY)
        for each in [
            "P1: decide.decide takes []",
            "P8: gateverbs.lookup is no total match on the verb",
            "P11: there is no retrying.with_retries",
        ]:
            assert_that(found, has_item(each))

    def test_the_path_proofs_exit_one_with_no_package(self) -> None:
        """At a root with no ``src/pitboss`` the proofs exit 1."""
        with tempfile.TemporaryDirectory() as base:
            assert_that(_status_of_main(_bare_root(base)), equal_to(1))

    def test_the_seeds_exit_one_with_no_package(self) -> None:
        """``python -m pitboss.proofseeds`` exits 1 where the proofs do not hold."""
        with tempfile.TemporaryDirectory() as base:
            assert_that(_status_of_seeds(_bare_root(base)), equal_to(1))


class TestModes(unittest.TestCase):
    """Plan 6.3, P4: every declared command line maps onto a mode."""

    def test_a_command_line_that_exits_is_a_finding(self) -> None:
        """A parse that exits names the command line."""
        found = modeproof.images(_exits, NEXT_ONLY)
        assert_that(found, has_item("P4: next exits 2 instead of a mode"))

    def test_a_mode_no_command_line_reaches_is_a_finding(self) -> None:
        """A table with only ``next`` leaves ``Sweep`` unreached."""
        found = modeproof.images(_no_mode, NEXT_ONLY)
        assert_that(found, has_item("P4: no command line is Sweep"))

    def test_an_optional_argument_is_varied(self) -> None:
        """``next`` is read with no ticket and with one."""
        labels = [label for label, _ in modeproof.command_lines(NEXT_ONLY)]
        assert_that(labels, equal_to(["next", f"next ticket={modeproof.ITEM}"]))

    def test_a_registration_that_is_no_wrapper_has_no_arguments(self) -> None:
        """A command registered as a bare function is read with no argument."""
        lines = list(modeproof.command_lines({"next": [print]}))
        assert_that([label for label, _ in lines], equal_to(["next"]))

    def test_a_parse_that_gives_no_mode_is_a_finding(self) -> None:
        """A command line mapped to a value of another type names that type."""
        found = modeproof.images(_not_a_mode, NEXT_ONLY)
        assert_that(found, has_item("P4: next is Repo, no mode"))

    def test_p4_names_each_finding_and_exits_one(self) -> None:
        """``modeproof.main`` prints each finding and exits 1 when one is found."""
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            status = modeproof.main(ROOT, _exits)
        assert_that(status, equal_to(1))
        assert_that(printed.getvalue(), contains_string("exits 2 instead of a mode"))

    def test_the_seeds_find_a_parse_that_reaches_every_mode(self) -> None:
        """Plan 6.5: P4's seed leaves a mode unreached; the real parse does not."""
        found = proofseeds.missed(TEXTS, cli_parser.table(), mode.parse)
        said = "P4: a parse that leaves a mode with no image is not found"
        assert_that(found, equal_to([said]))


class TestEdits(unittest.TestCase):
    """Plan 6.3: each proof finds the one edit that breaks its property."""

    def test_p3_a_read_failure_that_exits_zero_is_a_finding(self) -> None:
        """The one catch of ``ReadFailed`` must exit nonzero."""
        old = "            raise SystemExit(1) from failed\n"
        new = old.replace("(1)", "(0)")
        found = decideproofs.no_partial_world(_edited("cli_parser.py", old, new))
        said = "P3: cli_parser catches ReadFailed without a nonzero exit"
        assert_that(found, has_item(said))

    def test_p5_a_projection_of_another_value_is_a_finding(self) -> None:
        """A projection is given the decisions, nothing else."""
        new = "from . import project\n\nproject.by_item(made)\n"
        found = pathproofs.same_answer(_edited("extra.py", "", new))
        assert_that(found, has_item("P5: extra:3 projects made"))

    def test_p7a_an_optional_verb_is_a_finding(self) -> None:
        """A decision always carries its verb."""
        old = "    verb: str\n    item: str\n    title: str\n"
        new = old.replace("verb: str", "verb: str | None")
        found = decideproofs.no_wait(_edited("answer.py", old, new))
        assert_that(found, has_item("P7: Decision.verb is optional"))

    def test_p7a_a_reason_field_is_a_finding(self) -> None:
        """A decision has no field for a reason not to act."""
        old = "    verb: str\n    item: str\n    title: str\n"
        found = decideproofs.no_wait(_edited("answer.py", old, old + "    why: str\n"))
        assert_that(found, has_item("P7: Decision has a reason field why"))

    def test_p7d_another_guarded_arm_is_not_the_exhausted_one(self) -> None:
        """Only ``case world.Exhausted() if not ...`` is the arm of NotEnoughWork."""
        # before the real arm, so the walk reaches both guarded arms first
        new = GUARDED.lstrip() + "\n\ndef _answer("
        found = decideproofs.no_wait(_edited("decide.py", "def _answer(", new))
        assert_that(found, equal_to([]))

    def test_p8_a_lookup_of_another_type_is_a_finding(self) -> None:
        """Act looks its verb up in the decisions."""
        old = "def lookup(decided: answer.Decided,"
        new = "def lookup(decided: object,"
        found = decideproofs.act_agrees(_edited("gateverbs.py", old, new))
        said = "P8: gateverbs.lookup does not take the decisions"
        assert_that(found, has_item(said))

    def test_p8_each_verb_is_matched_applied_and_looked_up(self) -> None:
        """Every verb is one the lookup matches and act applies, and run looks it up."""
        lookup = "found = gateverbs.lookup("
        seeds = {
            ("actverbs.py", '    "ack": actwrite.ack,\n', ""): "verb ack has nothing",
            ("gateverbs.py", '    ACK = "ack"\n', ""): "act verb ack is no verb",
            ("actverbs.py", lookup, lookup.replace("(", "_none(")): "does not look",
        }
        for (path, old, new), said in seeds.items():
            found = decideproofs.act_agrees(_edited(path, old, new))
            assert_that("\n".join(found), contains_string(f"P8: {said}"))

    def test_p8_a_totalverdict_module_is_a_finding(self) -> None:
        """There is no second verdict."""
        found = decideproofs.act_agrees(_edited("totalverdict.py", "", "\n"))
        assert_that(found, has_item("P8: the totalverdict module exists"))


class TestOneParse(unittest.TestCase):
    """Plan 6.1: in what decide reaches, only the parsers read JSON."""

    def test_6_1_a_row_that_reads_json_is_a_finding(self) -> None:
        """A row module that imports ``totaljson`` is named."""
        new = "\nfrom . import totaljson\n"
        found = pathproofs.one_parse(_edited("gaterows.py", "", new))
        assert_that(found, equal_to(["6.1: gaterows reads JSON; only the parsers do"]))


class TestNoCheckIn(unittest.TestCase):
    """Plan 6.5: no check-in decision."""

    def test_6_5_decide_reaches_no_check_in(self) -> None:
        """Only the ledger's record of the last post names a check-in."""
        package = proofsource.of_texts(TEXTS)
        reached = proofsource.closure(package, "decide")
        named = sorted(
            proofsource.short(each)
            for each in reached
            if re.search(r"(?i)check-?in", TEXTS.get(_path_of(each), ""))
        )
        assert_that(named, equal_to(["slotbook"]))
