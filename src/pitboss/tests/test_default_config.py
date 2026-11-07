"""A command with no configuration argument finds one (keyword: default-config)."""

import argparse
import functools
import pathlib
import shutil
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import cli_parser, configfile
from . import cleanruns, cleanworld, fakes, fixeddisk, world

# Each command that takes a configuration: the words before it, the words after it.
COMMANDS = (
    ("clean", (), ()),
    ("clean-container", (), ()),
    ("clean-worktrees", (), ()),
    ("cancel-stale-runs", (), ()),
    ("sweep", (), ()),
    ("pressure", (), ()),
    ("queued", (), ()),
    ("ruling-summary", (), ()),
    ("push", (), ()),
    ("sync", (), ()),
    ("next", (), ()),
    ("analyze-red", (), ("owner/repo", "check.yml", "--output", "out.md")),
    ("review-form", (), ("owner/repo",)),
    ("slots", ("check",), ()),
)


def parsed(
    command: tuple[str, Sequence[str], Sequence[str]], *middle: str
) -> argparse.Namespace:
    """What a command line parses to.

    Args:
        command: the command, the words before the configuration, the words after.
        *middle: the configuration, or nothing.

    Returns:
        The arguments.
    """
    name, before, after = command
    made = cli_parser.make_parser(fixeddisk.fixed_usage)
    return made.parse_args([name, *before, *middle, *after])


def written(directory: pathlib.Path, *names: str) -> Sequence[pathlib.Path]:
    """Write empty files.

    Args:
        directory: where the names are.
        *names: the names, with parent directories.

    Returns:
        The files.
    """
    files = [directory / each for each in names]
    for each in files:
        each.parent.mkdir(parents=True, exist_ok=True)
        each.write_text("")
    return files


def default_in(directory: pathlib.Path) -> pathlib.Path:
    """The file a bare command finds from a directory.

    Args:
        directory: the working directory.

    Returns:
        The file.
    """
    return configfile.find_default(directory)


def found_world() -> world.World:
    """A world whose workspace holds the configuration a bare command finds.

    Returns:
        The world.
    """
    here = cleanworld.full_world().here
    shutil.copyfile(here.config, here.workspace / "pitboss.toml")
    return here


def bare_run(here: world.World, *more: str) -> world.Result:
    """Run ``clean-container`` with no configuration argument.

    Args:
        here: the world.
        *more: more arguments.

    Returns:
        What it did.
    """
    return world.invoke(here, "clean-container", *cleanworld.NO_MARKER, *more)


class TestParsing(unittest.TestCase):
    """Every command that takes a configuration takes none, or one."""

    def test_no_argument_and_an_explicit_one(self) -> None:
        """Without it ``config`` is None; with it, the word given."""
        found = [(parsed(c).config, parsed(c, "x.toml").config) for c in COMMANDS]
        assert_that(found, equal_to([(None, "x.toml")] * len(COMMANDS)))

    def test_words_after_the_configuration(self) -> None:
        """With a configuration, the words after it are git's and the ticket."""
        pushed = parsed(("push", (), ("origin", "branch")), "x.toml")
        asked = parsed(("next", (), ("#12",)), "x.toml")
        assert_that(
            (pushed.git_arguments, asked.ticket),
            equal_to((["origin", "branch"], "#12")),
        )


class TestFinding(unittest.TestCase):
    """The file a command with no argument uses."""

    def test_names_in_order_up_the_parents(self) -> None:
        """A root file comes before ``.claude/pitboss``; the nearest directory first."""
        top = fakes.directory() / "quire"
        inner = top / "a" / "b"
        inner.mkdir(parents=True)
        steps = (".claude/pitboss/pitboss.toml", "quire.toml", "pitboss.toml")
        found = []
        for name in steps:
            written(top, name)
            found.append(default_in(inner))
        written(inner, "pitboss.toml")
        found.append(default_in(inner))
        expected = [top / each for each in steps]
        assert_that(found, equal_to([*expected, inner / "pitboss.toml"]))

    def test_none_says_where_it_looked(self) -> None:
        """The message names the variable and the places."""
        inner = fakes.directory() / "empty"
        inner.mkdir()
        message = fakes.error_of(functools.partial(default_in, inner))
        places = ["pitboss.toml", "empty.toml", ".claude/pitboss/empty.toml"]
        assert_that(
            [each in message for each in ["$PITBOSS_CONFIG", *places]],
            equal_to([True] * 4),
        )

    def test_argument_then_variable_then_search(self) -> None:
        """The argument wins over ``PITBOSS_CONFIG``, which wins over the search."""
        directory = fakes.directory()
        (found,) = written(directory, "pitboss.toml")

        def name(config: str | None, env: Mapping[str, str]) -> str:
            args = argparse.Namespace(config=config, env={"PWD": str(directory), **env})
            return configfile.named(args)

        viable = {"PITBOSS_CONFIG": "env.toml"}
        assert_that(
            [name("x.toml", viable), name(None, viable), name(None, {})],
            equal_to(["x.toml", "env.toml", str(found)]),
        )


class TestRunning(unittest.TestCase):
    """``clean-container`` runs the same with no argument and with one."""

    def test_bare_equals_explicit(self) -> None:
        """The bare form finds ``pitboss.toml`` and does what the explicit one does."""
        here = found_world()
        bare, explicit = bare_run(here), cleanruns.clean(here)
        assert_that(
            [(each.code, each.out, each.err) for each in (bare, explicit)],
            equal_to([(explicit.code, explicit.out, explicit.err)] * 2),
        )
        assert_that("REMOVED PATH" in bare.out, equal_to(True))

    def test_bare_cleans_with_no_dry_run(self) -> None:
        """The auto-approved ``--no-dry-run`` form removes the safe paths."""
        here = found_world()
        planned = cleanruns.listed(here)
        done = cleanworld.lines_of(bare_run(here, "--no-dry-run").out, "REMOVED PATH")
        absent = [not pathlib.Path(each).exists() for each in done]
        assert_that(
            (list(done), absent), equal_to((list(planned), [True] * len(absent)))
        )

    def test_missing_configuration_says_where_it_looked(self) -> None:
        """With no file anywhere the run stops with the places it looked."""
        here = cleanworld.full_world().here
        said = fakes.error_of(functools.partial(bare_run, here))
        assert_that("$PITBOSS_CONFIG" in said, equal_to(True))
