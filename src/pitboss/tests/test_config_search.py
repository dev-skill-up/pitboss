"""The file a command with no configuration finds (keyword: default-config)."""

import argparse
import functools
import pathlib
import tempfile
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import configfile, configsearch
from . import configcases, fakes, world

QUIRE = "https://github.com/owner/quire.git"
# the tests' temporary directories are inside a checkout: git does not look above
CEILING = [pathlib.Path(tempfile.gettempdir())]
repository = functools.partial(configsearch.repository_name, ceiling=CEILING)
find = functools.partial(configsearch.find_default, ceiling=CEILING)


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


checkout = configcases.checkout


def quire_world() -> world.World:
    """A world whose clone, and so its worktree, came from ``quire``.

    Returns:
        The world.
    """
    here = world.make_world()
    fakes.run_git(here.clone, "remote", "set-url", "origin", QUIRE)
    return here


class TestRepositoryName(unittest.TestCase):
    """The name of ``<name>.toml`` is the repository's, not the directory's."""

    def test_the_origin_url_in_each_form(self) -> None:
        """A url, an ssh url and a url with a slash at the end."""
        forms = [QUIRE, "git@github.com:owner/quire.git", "https://x.org/o/quire/"]
        found = [repository(checkout("work-1", each)) for each in forms]
        assert_that(found, equal_to(["quire"] * 3))

    def test_no_origin_is_the_name_of_the_top_directory(self) -> None:
        """With no origin the checkout's directory, from any directory in it."""
        top = checkout("quire", None)
        (top / "a").mkdir()
        nameless = checkout("other", "/")
        found = [repository(top / "a"), repository(nameless)]
        assert_that(found, equal_to(["quire", "other"]))

    def test_outside_a_checkout_it_is_the_directory(self) -> None:
        """No ``.git`` below the ceiling: the directory the command runs in."""
        loose = fakes.directory() / "plain"
        loose.mkdir()
        assert_that(repository(loose), equal_to("plain"))

    def test_a_worktree_reads_the_origin_of_its_clone(self) -> None:
        """A worktree's ``.git`` is a file; the origin is in the clone's config."""
        assert_that(repository(quire_world().worktree), equal_to("quire"))

    def test_the_ceiling_variable_lists_directories(self) -> None:
        """``GIT_CEILING_DIRECTORIES`` is a list of paths; none is no ceiling."""
        listed = configsearch.ceilings({"GIT_CEILING_DIRECTORIES": "/a:/b::/c"})
        assert_that(
            listed, equal_to([pathlib.Path(each) for each in ("/a", "/b", "/c")])
        )
        assert_that(configsearch.ceilings({}), equal_to([]))


class TestFinding(unittest.TestCase):
    """The file a command with no argument uses."""

    def test_names_in_order_up_the_parents(self) -> None:
        """A root file comes before ``.claude/pitboss``; the nearest directory first."""
        top = checkout("work-3", QUIRE)
        inner = top / "a" / "b"
        inner.mkdir(parents=True)
        steps = (".claude/pitboss/pitboss.toml", "quire.toml", "pitboss.toml")
        found = []
        for name in steps:
            written(top, name)
            found.append(find(inner))
        written(inner, "pitboss.toml")
        found.append(find(inner))
        expected = [top / each for each in steps]
        assert_that(found, equal_to([*expected, inner / "pitboss.toml"]))

    def test_a_directory_named_otherwise_finds_the_repository_file(self) -> None:
        """``quire.toml`` is found in a directory that is not called ``quire``."""
        top = checkout("pb-307", QUIRE)
        written(top, "pb-307.toml")
        (wanted,) = written(top, "quire.toml")
        assert_that(find(top), equal_to(wanted))

    def test_a_worktree_of_another_name_runs_a_command_bare(self) -> None:
        """``slots check`` in a worktree finds ``quire.toml`` at its root."""
        here = quire_world()
        configcases.copy_config(here, here.worktree / "quire.toml")
        ran = world.invoke(here, "slots", "check", directory=here.worktree)
        assert_that((ran.code, ran.err.count("DEPRECATED")), equal_to((0, 0)))

    def test_none_says_where_it_looked(self) -> None:
        """The message names the variable, the places and ``--config``."""
        inner = fakes.directory() / "empty"
        inner.mkdir()
        message = fakes.error_of(functools.partial(find, inner))
        said = [
            "$PITBOSS_CONFIG",
            "--config",
            "empty.toml",
            ".claude/pitboss/empty.toml",
        ]
        assert_that([each in message for each in said], equal_to([True] * 4))

    def test_argument_then_variable_then_search(self) -> None:
        """``--config`` wins over ``PITBOSS_CONFIG``, which wins over the search."""
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
