"""A command with no configuration argument finds one (keyword: default-config)."""

import os
import pathlib
import shutil
import subprocess
import sys
import unittest
from typing import Sequence, cast

from gather.api import Wrapper, unique
from hamcrest import assert_that, equal_to

from .. import ENTRY_DATA, cli_parser, commandscan, configsettle
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
        expected = {each.before[0] for each in CASES} | {"lint"}
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
            runs = [configcases.form_run(case, form) for form in configcases.FORMS]
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
            runs = [configcases.form_run(case, form)[1] for form in configcases.FORMS]
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


def missing(case: configcases.Case, directory: pathlib.Path) -> tuple[int, bool, bool]:
    """Run a command in an empty directory with no configuration.

    Args:
        case: the command.
        directory: the directory it runs in.

    Returns:
        The exit status, and whether standard error names ``$PITBOSS_CONFIG``
        and the file ``pitboss.toml`` of the directory.
    """
    env = {key: value for key, value in os.environ.items() if key != "PITBOSS_CONFIG"}
    # a PATH with git only: the fetch by name (fetched-config) finds no gh
    tools = fakes.directory()
    (tools / "git").symlink_to(str(shutil.which("git")))
    env.update(PWD=str(directory), HOME=str(directory), PATH=str(tools))
    done = subprocess.run(
        [sys.executable, "-m", "pitboss", *case.before, *case.after],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    place = str(directory / "pitboss.toml")
    return (done.returncode, "$PITBOSS_CONFIG" in done.stderr, place in done.stderr)


class TestMissingConfiguration(unittest.TestCase):
    """With no configuration anywhere a command says where it looked."""

    def test_each_command_says_where_it_looked(self) -> None:
        """Exit 1 (the uncaught error), and the variable and the places on stderr."""
        found = []
        for case in CASES:
            found.append(missing(case, fakes.directory()))
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
