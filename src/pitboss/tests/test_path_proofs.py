"""The proofs of the one path, P1 to P11, on the package and its seeds (plan 6.3)."""

import argparse
import contextlib
import io
import pathlib
import tempfile
import unittest
from typing import Mapping

from gather import commands as gather_commands
from gather.api import Wrapper
from hamcrest import assert_that, equal_to, has_item

from .. import cli_parser, config, mode, modeproof, pathproofs, proofseeds, proofsource

# the repository: src/pitboss/pathproofs.py is two levels below it
ROOT = pathlib.Path(pathproofs.__file__).resolve().parents[2]
EMPTY = proofsource.of_texts({})
TICKET = gather_commands.add_argument("ticket", nargs="?")
NEXT_ONLY = {"next": [Wrapper(original=print, extra=(TICKET,))]}


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
    return mode.WhatNext(asked=mode.Asked.NEXT)


class TestThePackage(unittest.TestCase):
    """Plan 6.3 and 6.5: the proofs hold on the package and find each seed."""

    def test_every_proof_holds_and_every_seed_is_found(self) -> None:
        """P1 to P11 hold, and each fails on its one seeded edit."""
        missed = proofseeds.missed(proofsource.read(ROOT), cli_parser.table())
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
