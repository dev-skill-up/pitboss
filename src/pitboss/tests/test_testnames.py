"""The test names a PR body cites against the head's tree (pitboss#189)."""

import pathlib
import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import testnames
from . import fakes
from .linting import BODY, lines, lint, write_text

PLAN = "## Plan\n\nThe test `{name}` covers it.\n\n"
TESTS = (
    "class TestIt:\n    def test_exists(self):\n        pass\n\n"
    "    async def test_later(self):\n        pass\n"
)


def checkout() -> pathlib.Path:
    """A head's checkout with one test module and a hidden directory.

    Returns:
        Its directory.
    """
    root = fakes.directory()
    fakes.write(root / "tests" / "test_module.py", TESTS)
    for where in (".nox/other.py", "build/made.py", "notes.txt"):
        fakes.write(root / where, "def test_hidden():\n    pass\n")
    return root


def cite(name: str) -> str:
    """A good body whose Plan cites a test.

    Args:
        name: the test's name.

    Returns:
        The body.
    """
    return BODY + "\n" + PLAN.format(name=name)


def run(body: str, root: pathlib.Path) -> tuple[object, str]:
    """Run ``pitboss lint pr-body`` with the head's checkout.

    Args:
        body: the body.
        root: the checkout.

    Returns:
        The exit code and the output.
    """
    done = lint("pr-body", write_text("body.md", body), "--checkout", str(root))
    return done.code, done.out


class TestTestNames(unittest.TestCase):
    """``pr-body --checkout`` and the ``test-name`` check."""

    def test_a_missing_name_is_refused_naming_it(self) -> None:
        """The finding names the identifier and the check."""
        code, out = run(cite("test_two_rejections_at_one_head"), checkout())
        assert_that(code, equal_to(1))
        assert_that(out, contains_string("test_two_rejections_at_one_head"))
        assert_that(out, contains_string("(test-name)"))

    def test_an_existing_name_passes(self) -> None:
        """A name with a ``def`` in the tree, async or not, is ok."""
        for name in ("test_exists", "test_later", "test_module"):
            with self.subTest(name):
                assert_that(run(cite(name), checkout()), equal_to((0, "ok\n")))

    def test_a_hidden_directory_and_a_text_file_have_no_tests(self) -> None:
        """Only Python files outside hidden and build directories count."""
        assert_that(run(cite("test_hidden"), checkout())[0], equal_to(1))

    def test_execution_is_read_and_evidence_is_not(self) -> None:
        """A name under Execution is checked; one under Evidence is not."""
        under = "## Execution\n\nRan `test_gone`.\n\n"
        assert_that(run(BODY + "\n" + under, checkout())[0], equal_to(1))
        evidence = BODY + "\nsee test_gone\n"
        assert_that(run(evidence, checkout())[0], equal_to(0))

    def test_a_subheading_stays_in_its_section(self) -> None:
        """A deeper heading is part of the Plan; a same-level one ends it."""
        deeper = "## Plan\n\n### Tests\n\ntest_gone\n\n"
        assert_that(testnames.cited(deeper + BODY), equal_to(["test_gone"]))
        ended = "## Plan\n\ntext\n\n## Notes\n\ntest_gone\n\n"
        assert_that(testnames.cited(ended + BODY), equal_to([]))

    def test_a_comment_in_a_fenced_block_is_no_heading(self) -> None:
        """A name cited after a block holding a ``#`` line is still refused."""
        block = "```sh\n# build it\nmake\n```\n\n"
        plan = "## Plan\n\n" + block + "The test `test_gone` covers it.\n\n"
        assert_that(testnames.cited(plan + BODY), equal_to(["test_gone"]))
        assert_that(run(BODY + "\n" + plan, checkout())[0], equal_to(1))
        open_block = "## Plan\n\n~~~\n# never closed\ntest_gone\n"
        assert_that(testnames.cited(open_block), equal_to(["test_gone"]))

    def test_a_name_cited_twice_is_one_finding(self) -> None:
        """Each identifier is named once."""
        twice = "## Plan\n\ntest_gone and test_gone\n\n## Execution\n\ntest_gone\n"
        found = testnames.findings("body", twice, checkout(), set())
        assert_that(found, has_length(1))

    def test_no_checkout_is_not_checked(self) -> None:
        """Without ``--checkout`` the body is judged by its form alone."""
        done = lint("pr-body", write_text("body.md", cite("test_gone")))
        assert_that(lines(done), equal_to(["ok"]))

    def test_a_checkout_that_is_not_a_directory_is_a_usage_error(self) -> None:
        """Exit 2 names the option."""
        missing = fakes.directory() / "absent"
        done = lint("pr-body", write_text("body.md", BODY), "--checkout", str(missing))
        assert_that(done.code, equal_to(2))
        assert_that(done.err, contains_string("--checkout"))
