"""``pitboss hook pre-push`` (keyword: pre-push-hook, T50)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import hook_commands
from . import fakes, world

ZERO = "0" * 40
SHA = "a" * 40
PUSH = f"refs/heads/b {SHA} refs/heads/b {ZERO}\n"
DELETE = f"(delete) {ZERO} refs/heads/b {SHA}\n"


def check(name: str, script: str, fix: str = "") -> str:
    """The TOML of a check whose script is given.

    Args:
        name: the check's name.
        script: the shell it runs.
        fix: the fix it names.

    Returns:
        The TOML.
    """
    return (
        f'\n[[pre_push]]\nname = "{name}"\ncommand = ["sh", "-c", {script!r}]\n'
        f'ok = "fine"\nfix = "{fix}"\n'
    )


def run_hook(declared: str, refs: str) -> world.Result:
    """Run the hook in a world whose configuration declares checks.

    Args:
        declared: the TOML to add.
        refs: the lines git gives on standard input.

    Returns:
        What it did.
    """
    here = world.make_world()
    with open(here.config, "a", encoding="utf-8") as handle:
        handle.write(declared)
    lines = fakes.directory() / "refs.txt"
    lines.write_text(refs, encoding="utf-8")
    argv = ["hook", "pre-push", "origin", "url", "--refs", str(lines)]
    return world.invoke(here, *argv, "--config", here.config, directory=here.clone)


class TestHook(unittest.TestCase):
    """A passing run, a failing check and a deletion push."""

    def test_t50_a_passing_run_prints_nothing_and_exits_0(self) -> None:
        """Every check printed its ok."""
        done = run_hook(check("one", "echo fine") + check("two", "echo fine"), PUSH)
        assert_that((done.code, done.out), equal_to((0, "")))

    def test_t50_the_first_failing_check_is_named_with_its_fix(self) -> None:
        """The format, the number, and the stop at the first."""
        declared = check("one", "echo fine") + check("two", "echo bad; exit 1", "do it")
        declared += check("three", "echo fine")
        done = run_hook(declared, PUSH)
        assert_that(done.code, equal_to(1))
        assert_that(done.out, contains_string("pre-push: check 2 (two) failed:"))
        assert_that(done.out, contains_string("fix: do it"))
        assert_that("three" in done.out, equal_to(False))

    def test_t50_a_check_without_a_fix_still_says_one(self) -> None:
        """The default fix."""
        done = run_hook(check("one", "exit 1"), PUSH)
        assert_that(done.out, contains_string("fix: run the check by hand"))

    def test_t50_a_deletion_push_is_not_checked(self) -> None:
        """A deleted ref skips the checks, a mixed push does not."""
        declared = check("one", "exit 1")
        assert_that(run_hook(declared, DELETE).code, equal_to(0))
        assert_that(run_hook(declared, DELETE + PUSH).code, equal_to(1))

    def test_t50_ref_lines_are_read(self) -> None:
        """No line at all is a push; a line with one word is ignored."""
        assert_that(hook_commands.pushes_something(""), equal_to(True))
        assert_that(hook_commands.pushes_something("x\n"), equal_to(True))
