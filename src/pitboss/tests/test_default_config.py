"""A command with no configuration argument finds one (keyword: default-config)."""

import dataclasses
import os
import pathlib
import shutil
import subprocess
import sys
import unittest
from typing import Sequence, cast

from gather.api import Wrapper, unique
from hamcrest import assert_that, equal_to, is_not

from .. import ENTRY_DATA, cli_parser, commandscan, configsettle, disk
from . import configcases, fakes, fixeddisk, world

CASES = configcases.CASES


def registered() -> Sequence[str]:
    """The commands registered with a configuration, as the first word or ``--config``.

    Returns:
        Their names, sorted.
    """
    commands = unique(commandscan.scanned(ENTRY_DATA.collector.collect))
    named = {
        name: configsettle.names_of(cast(Wrapper, each).extra)  # noqa: SLD203
        for name, each in commands.items()
    }
    return sorted(
        name for name, words in named.items() if {"config", "--config"} & set(words)
    )


class TestCommandsWithAConfiguration(unittest.TestCase):
    """The commands the tests run are the commands the parser has."""

    def test_every_command_with_a_configuration_is_run_here(self) -> None:
        """A new command that takes a configuration must be added to ``CASES``."""
        # these two have only the option, so no old first word to run in four
        # forms; lint is run below, plan-check by test_ci_pointer_check.py and
        # pins-review by test_pins_review.py
        only_option = {"lint", "plan-check", "pins-review"}
        expected = {each.before[0] for each in CASES} | only_option
        assert_that(registered(), equal_to(sorted(expected)))

    def test_each_command_takes_the_option(self) -> None:
        """``--config`` is parsed by every command that has the first word."""
        made = cli_parser.make_parser(fixeddisk.fixed_usage)
        words = [[*each.before, "--config", "c.toml", *each.after] for each in CASES]
        found = [made.parse_args(each).config_option for each in words]
        assert_that(found, equal_to(["c.toml"] * len(CASES)))


class TestFourForms(unittest.TestCase):
    """A command runs the same bare, with the option, the old word and the variable."""

    def test_every_command_runs_in_each_form(self) -> None:
        """The exit code, the output and the error output of the forms are equal."""
        found = {}
        for case in CASES:
            command = case.before[0]
            runs = [
                configcases.every_run()[command, form] for form in configcases.FORMS
            ]
            found[command] = [
                configcases.seen(here, result, command) for here, result in runs
            ]
        same = {name: [seen[0]] * len(seen) for name, seen in found.items()}
        assert_that(found, equal_to(same))

    def test_the_old_word_prints_the_deprecation_line_once(self) -> None:
        """Only the old first word says it is deprecated, and once."""
        said = {}
        for case in CASES:
            line = configcases.deprecation(case.before[0])
            runs = [
                configcases.every_run()[case.before[0], form].result
                for form in configcases.FORMS
            ]
            said[case.before[0]] = [each.err.count(line) for each in runs]
        assert_that(said, equal_to({each.before[0]: [0, 0, 1, 0] for each in CASES}))

    def test_lint_runs_bare_with_the_option_and_with_the_variable(self) -> None:
        """``lint`` finds its configuration by the search and by the variable."""
        case = configcases.LINT
        forms = ("bare", "option", "variable")
        runs = [configcases.form_run(case, form) for form in forms]
        results = [configcases.seen(here, found, "lint") for here, found in runs]
        assert_that(results, equal_to([results[0]] * 3))
        assert_that(results[0][2], equal_to(1))


def ran_missing(
    case: configcases.Case, directory: pathlib.Path, tools: pathlib.Path
) -> subprocess.CompletedProcess[str]:
    """Run a command in an empty directory with no configuration.

    Args:
        case: the command.
        directory: the directory it runs in.
        tools: an empty directory, which becomes the PATH with git only.

    Returns:
        The finished process, its output captured.
    """
    env = {key: value for key, value in os.environ.items() if key != "PITBOSS_CONFIG"}
    # a PATH with git only: the fetch by name (fetched-config) finds no gh
    (tools / "git").symlink_to(str(shutil.which("git")))
    # the kept copy of a fetched configuration is under $XDG_CACHE_HOME, else HOME:
    # both are this case's own, so no copy of the machine is found (keyword: flake-368)
    own = {"PWD": str(directory), "HOME": str(directory)}
    env.update(own, XDG_CACHE_HOME=str(directory / ".cache"), PATH=str(tools))
    return subprocess.run(
        [sys.executable, "-m", "pitboss", *case.before, *case.after],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def missing(
    case: configcases.Case, directory: pathlib.Path, tools: pathlib.Path
) -> Sequence[object]:
    """Run a command with no configuration and say what its error output names.

    Args:
        case: the command.
        directory: the directory it runs in.
        tools: an empty directory, which becomes the PATH with git only.

    Returns:
        The exit status, and whether standard error names ``$PITBOSS_CONFIG``
        and the file ``pitboss.toml`` of the directory; when either is not as
        expected, also the command line, the standard error and the directory,
        so a failure shows them (keyword: flake-368).
    """
    done = ran_missing(case, directory, tools)
    names = ("$PITBOSS_CONFIG", str(directory / "pitboss.toml"))
    found = (done.returncode, *(each in done.stderr for each in names))
    return (
        found
        if found == (1, True, True)
        else (*found, done.args, done.stderr, str(directory))
    )


class TestMissingConfiguration(unittest.TestCase):
    """With no configuration anywhere a command says where it looked."""

    def test_each_command_says_where_it_looked(self) -> None:
        """Exit 1 (the uncaught error), and the variable and the places on stderr."""
        # one process at a time: a pool of threads forking while the others copy
        # os.environ raced (keyword: flake-368, pitboss#368)
        found = [missing(each, fakes.directory(), fakes.directory()) for each in CASES]
        assert_that(found, equal_to([(1, True, True)] * len(CASES)))

    def test_lint_keeps_its_generic_forms_and_says_where_it_looked(self) -> None:
        """``lint`` still checks with no configuration, and names the places."""
        here = world.make_world()
        found = configcases.run(here, ["lint", "text", os.devnull])
        places = ("$PITBOSS_CONFIG", str(here.workspace / "pitboss.toml"))
        assert_that(
            (found.code, *(each in found.err for each in places)),
            equal_to((0, True, True)),
        )


def free_of(gibibytes: int) -> disk.Reader:
    """A disk reader whose disk has a free space.

    Args:
        gibibytes: the free space, in GiB.

    Returns:
        The reader, which gives that figure for every path.
    """

    def read(path: pathlib.Path) -> disk.Usage:
        total = 100 * fixeddisk.GIBIBYTE
        free = gibibytes * fixeddisk.GIBIBYTE
        return disk.Usage(total, total - free, free)

    return read


def cleaned_with(gibibytes: int) -> tuple[world.World, world.Result]:
    """Run the ``clean-container`` case in a world whose disk has a free space.

    Args:
        gibibytes: the free space, in GiB.

    Returns:
        The world and what the command did.
    """
    case = CASES[1]
    made = configcases.placed(case.make, configcases.SEARCHED)
    here = dataclasses.replace(made, usage=free_of(gibibytes))
    words = configcases.with_form(case.before, case.after, here, "bare")
    return here, configcases.run(here, words)


class TestFreeDiskFigures(unittest.TestCase):
    """The free-disk figures of a clean are the world's disk reading (pitboss#316)."""

    def test_clean_container_says_the_disk_reading_it_was_given(self) -> None:
        """The figures are the injected ones, not the machine's."""
        lines = [
            [each for each in cleaned_with(size)[1].out.splitlines() if "disk:" in each]
            for size in (20, 30)
        ]
        assert_that(
            lines,
            equal_to(
                [
                    ["disk: 20.0 GiB free before, 20.0 GiB after"],
                    ["disk: 30.0 GiB free before, 30.0 GiB after"],
                ]
            ),
        )

    def test_the_same_case_is_equal_with_different_figures(self) -> None:
        """Two runs of the case on disks of different free space are seen alike."""
        small, large = cleaned_with(20), cleaned_with(30)
        assert_that(small[1].out, is_not(equal_to(large[1].out)))
        assert_that(
            configcases.seen(*small, "clean-container"),
            equal_to(configcases.seen(*large, "clean-container")),
        )

    def test_figures_of_both_lines_are_hidden(self) -> None:
        """``clean-container``'s line and the last line of ``clean`` are hidden."""
        texts = [
            "disk: 6.9 GiB free before, 6.8 GiB after\n",
            "x; disk free unknown before, 512.0 MiB after\n",
        ]
        assert_that(
            [configcases.free_disk_hidden(each) for each in texts],
            equal_to(
                [
                    "disk: <free> free before, <free> after\n",
                    "x; disk free <free> before, <free> after\n",
                ]
            ),
        )

    def test_two_outputs_differing_in_another_line_stay_different(self) -> None:
        """A different path, size or count is not hidden with the figures."""
        base = (
            "REMOVED PATH /a 1.0 GiB (x)\n"
            "clean: 6 paths removed, 1.0 GiB freed;"
            " disk free 6.9 GiB before, 6.9 GiB after\n"
        )
        others = [
            base.replace("/a", "/b"),
            base.replace("REMOVED PATH /a 1.0 GiB", "REMOVED PATH /a 2.0 GiB"),
            base.replace("6 paths", "7 paths"),
            base.replace("1.0 GiB freed", "2.0 GiB freed"),
            base.replace("disk free", "disk used"),
        ]
        hidden = configcases.free_disk_hidden
        assert_that(
            [hidden(each) == hidden(base) for each in others],
            equal_to([False] * len(others)),
        )
