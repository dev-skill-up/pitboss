"""P4, the modes proof, on the package and its seeds (plan 6.3)."""

import argparse
import contextlib
import io
import pathlib
import tempfile
import unittest
from typing import Mapping

from gather import commands as gather_commands
from gather.api import Wrapper
from hamcrest import assert_that, contains_string, equal_to, has_item

from .. import (
    cli_parser,
    config,
    mode,
    modeproof,
    proofseeds,
    proofsource,
)

# the repository: src/pitboss/modeproof.py is two levels below it
ROOT = pathlib.Path(modeproof.__file__).resolve().parents[2]
TICKET = gather_commands.add_argument("ticket", nargs="?")
NEXT_ONLY = {"next": [Wrapper(original=print, extra=(TICKET,))]}
TEXTS = proofsource.read(ROOT)


def _bare_root(base: str) -> pathlib.Path:
    # a repository whose package has no module
    (pathlib.Path(base) / "src" / "pitboss").mkdir(parents=True)
    return pathlib.Path(base)


def _status_of_seeds(root: pathlib.Path) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return proofseeds.main(root, NEXT_ONLY)


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
        """P4 holds, and each of its checks fails on its seeded edit."""
        missed = proofseeds.missed(TEXTS, cli_parser.table(), proofseeds.other_modes)
        assert_that(missed, equal_to([]))

    def test_p4_exits_zero_on_the_package(self) -> None:
        """``python -m pitboss.modeproof`` exits 0 at the repository's root."""
        with contextlib.redirect_stdout(io.StringIO()):
            status = modeproof.main(ROOT, mode.parse)
        assert_that(status, equal_to(0))


class TestNoPackage(unittest.TestCase):
    """Plan 6.3: a package that is gone is a finding."""

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
