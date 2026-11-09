"""``pitboss impact``: the hits of a phrase in the whole tree (pitboss#320)."""

import os
import pathlib
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import impact
from . import fakes, world
from .test_expand_commands import real_world

PHRASE = "plan lists each behaviour"
TREE: Mapping[str, str] = {
    "src/pkg/mod.py": f'"""Docstring.\n\nThe {PHRASE} the change alters."""\n',
    "doc/notes.md": "# Notes\n\nThe Plan LISTS EACH Behaviour.\n",
    "doc/wrapped.rst": "Text before the plan\nlists   each\n\tbehaviour of it.\n",
    "src/pkg/comment.py": "x = 1\n# the plan lists\n# each behaviour\n",
    "src/pkg/strings.py": 'TEXT = (\n    "the plan lists"\n    " each behaviour"\n)\n',
    "doc/quoted.md": "> the plan lists\n> * each |\n>   behaviour\n",
    "doc/nothing.md": "the plan lists each other behaviour\n",
    "README": "the plan lists each behaviour\n",
    "src/build/inside.txt": f"{PHRASE}\n",
}
LEFT_OUT: Mapping[str, str] = {
    ".git/config": PHRASE,
    "build/out.txt": PHRASE,
    "skill-zips/sweep.txt": PHRASE,
    "src/__pycache__/mod.txt": PHRASE,
    ".mypy_cache/meta.txt": PHRASE,
    ".nox/log.txt": PHRASE,
    "data/binary.bin": "\0" + PHRASE,
}
WANT = [
    "README:1:the plan lists each behaviour",
    "doc/notes.md:3:The Plan LISTS EACH Behaviour.",
    "doc/quoted.md:1:> the plan lists",
    "doc/wrapped.rst:1:Text before the plan",
    "src/build/inside.txt:1:plan lists each behaviour",
    "src/pkg/comment.py:2:# the plan lists",
    'src/pkg/mod.py:3:The plan lists each behaviour the change alters."""',
    'src/pkg/strings.py:2:    "the plan lists"',
]


def planted(tree: Mapping[str, str]) -> pathlib.Path:
    """Plant files in a new directory.

    Args:
        tree: the files, by path, with their text.

    Returns:
        The directory.
    """
    root = fakes.directory()
    for name, content in tree.items():
        fakes.write(root / name, content)
    return root


def shown(root: pathlib.Path, *phrases: str) -> Sequence[str]:
    """The hits as they are printed.

    Args:
        root: the tree.
        *phrases: the phrases.

    Returns:
        The lines.
    """
    return [impact.shown(each) for each in impact.hits_in(root, phrases)]


class TestSearch(unittest.TestCase):
    """The whole tree, a docstring, a markdown file and a wrapped sentence."""

    def test_every_form_of_the_sentence_is_a_hit_at_its_first_line(self) -> None:
        """Done-when: a docstring, a markdown file, a wrapped sentence."""
        root = planted({**TREE, **LEFT_OUT})
        assert_that(shown(root, PHRASE), equal_to(WANT))

    def test_the_left_out_places_are_the_only_ones(self) -> None:
        """Git, the build, the zips and the caches, and a binary file."""
        root = planted(LEFT_OUT)
        assert_that(shown(root, PHRASE), equal_to([]))

    def test_a_line_is_listed_once_for_any_number_of_phrases(self) -> None:
        """Two phrases, one of them twice on a line, and a second hit later."""
        root = planted({"a.txt": "one two one two\nnil\ntwo\n"})
        want = ["a.txt:1:one two one two", "a.txt:3:two"]
        assert_that(shown(root, "one", "two", "one"), equal_to(want))

    def test_the_text_keeps_its_indent_and_loses_its_trailing_space(self) -> None:
        """The line is the file's, not trimmed on the left."""
        root = planted({"a.txt": "  key  \r\nother\n"})
        assert_that(shown(root, "key"), equal_to(["a.txt:1:  key"]))

    def test_a_link_is_not_followed(self) -> None:
        """A symbolic link is no file of the tree."""
        root = planted({"real.txt": "key\n"})
        os.symlink(root / "real.txt", root / "link.txt")
        assert_that(shown(root, "key"), equal_to(["real.txt:1:key"]))

    def test_an_inline_code_span_is_part_of_the_break(self) -> None:
        """A docstring wraps before a literal in double backticks."""
        root = planted({"a.py": "Each row runs with\n``sh -c`` in a tree\n"})
        want = ["a.py:1:Each row runs with"]
        assert_that(shown(root, "runs with sh -c"), equal_to(want))

    def test_a_git_file_of_a_worktree_is_left_out(self) -> None:
        """A worktree has a file named .git, which is not searched."""
        root = planted({".git": "gitdir: key\n", "a.txt": "key\n"})
        assert_that(shown(root, "key"), equal_to(["a.txt:1:key"]))

    def test_a_phrase_with_no_word_is_refused(self) -> None:
        """Nothing to search for."""
        for each in ("", "  \n"):
            with self.assertRaises(impact.PhraseError):
                impact.expression(each)


def command(root: pathlib.Path, *argv: str) -> world.Result:
    """Run ``pitboss impact``.

    Args:
        root: the tree.
        *argv: the phrases and options.

    Returns:
        What it did.
    """
    return world.invoke(real_world(), "impact", "--root", str(root), *argv)


class TestCommand(unittest.TestCase):
    """The command prints the hits."""

    def test_it_prints_a_hit_a_line(self) -> None:
        """The same list as the search."""
        root = planted({**TREE, **LEFT_OUT})
        done = command(root, PHRASE)
        assert_that(
            [done.code, done.out.splitlines()],
            equal_to([0, WANT]),
        )

    def test_a_tree_without_a_hit_prints_nothing(self) -> None:
        """Exit status 0 and no output."""
        done = command(planted({"a": "b"}), "missing")
        assert_that([done.code, done.out], equal_to([0, ""]))

    def test_it_says_what_it_searched_and_hints_at_an_underscore_form(self) -> None:
        """Done-when (pitboss#317): a phrase with a space, a name with underscores."""
        root = planted({"a.py": "def come_first():\n    pass\n"})
        cases = {
            "a space": (
                "come first",
                ["searched: `come first`", "hint:", "`come_first`"],
            ),
            "the name": ("come_first", ["searched: `come_first`"]),
        }
        for name, (phrase, said) in cases.items():
            with self.subTest(name):
                done = command(root, phrase)
                assert_that(all(each in done.err for each in said), equal_to(True))
                assert_that(("hint:" in done.err), equal_to("hint:" in said))
        quiet = command(root, "come last", "come")
        assert_that(quiet.err.count("hint:"), equal_to(0))

    def test_usage_errors_are_status_2(self) -> None:
        """A root that is no directory, and a phrase with no word."""
        root = planted({"a": "b"})
        cases = {
            "root": (command(root / "none", "x"), "not a directory"),
            "phrase": (command(root, " "), "no word"),
        }
        for name, (done, said) in cases.items():
            with self.subTest(name):
                assert_that(done.code, equal_to(2))
                assert_that(done.err, contains_string(said))
