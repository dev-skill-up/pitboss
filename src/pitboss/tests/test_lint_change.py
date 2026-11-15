"""A changed lint with no new test the Plan cites is refused (pitboss#398)."""

import argparse
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import lintchange, plancheck_commands
from . import diffrepo
from .plancheckrun import body_of, passed, plan_check, refused_with
from .repositories import run_git

MODULE = "src/pitboss/lint.py"
TESTS = "src/pitboss/tests/test_lint.py"
OTHER_TESTS = "src/pitboss/tests/test_other.py"
BEFORE = (
    '"""Doc."""\n\n\ndef findings(x):\n    """Docstring."""\n    return x > 1\n'
    "\n\ndef helper(x):\n    return x\n"
)
AFTER = BEFORE.replace("x > 1", "x > 2")
PLAIN = BEFORE.replace("findings", "checked")
SOURCES = {
    "src/pitboss/__init__.py": "",
    "src/pitboss/tests/__init__.py": "",
    MODULE: AFTER,
    TESTS: "from .. import lint\n",
    OTHER_TESTS: "from .. import noxcheck\n",
    "src/pitboss/noxcheck.py": "",
}
CHANGED = f"diff --git a/{MODULE} b/{MODULE}\n--- a/{MODULE}\n+++ b/{MODULE}\n"
LOOSENED = CHANGED + "@@ -6 +6 @@\n-    return x > 1\n+    return x > 2\n"
ADDED = "@@ -0,0 +1 @@\n+def test_loosened():\n"


def with_test(path: str) -> str:
    """The loosened lint, and a test added to a test file.

    Args:
        path: the test file.

    Returns:
        The patch.
    """
    return (
        LOOSENED + f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{ADDED}"
    )


def found(
    patch: str, plan: str = "## Plan\n1. `rg x`\n", head: Mapping[str, str] = SOURCES
) -> Sequence[str]:
    """The findings of a patch.

    Args:
        patch: the patch.
        plan: the Plan section.
        head: the head's files.

    Returns:
        The findings.
    """
    return lintchange.findings(plan, patch, head)


class TestLintChange(unittest.TestCase):
    """The heuristic, on the module."""

    def test_a_loosened_condition_with_no_test_is_refused(self) -> None:
        """Done-when: the module and the function are named."""
        said = found(LOOSENED)
        assert_that(len(said), equal_to(1))
        assert_that(said[0], contains_string("`pitboss.lint` function `findings`"))
        assert_that(said[0], contains_string(f"`{MODULE}` line 6"))

    def test_a_test_the_plan_cites_makes_it_pass(self) -> None:
        """The accepted form: the test is added to a module that imports it."""
        plan = "## Plan\n1. `rg test_loosened`\n"
        assert_that(found(with_test(TESTS), plan), equal_to([]))

    def test_a_test_the_plan_does_not_cite_is_refused(self) -> None:
        """The nearest input: the test is there, no row names it."""
        assert_that(len(found(with_test(TESTS))), equal_to(1))

    def test_a_test_of_a_module_that_does_not_import_it_is_refused(self) -> None:
        """The nearest input: cited, but its file does not import the module."""
        plan = "## Plan\n1. `rg test_loosened`\n"
        assert_that(len(found(with_test(OTHER_TESTS), plan)), equal_to(1))

    def test_a_longer_name_is_not_the_cited_one(self) -> None:
        """A name that only starts with a cited one is another test."""
        plan = "## Plan\n1. `rg test_loosened_more`\n"
        assert_that(len(found(with_test(TESTS), plan)), equal_to(1))

    def test_a_comment_or_a_docstring_is_no_change(self) -> None:
        """The nearest input outside the rule: the text of a docstring changes."""
        patch = CHANGED + '@@ -5 +5 @@\n-    """Docstring."""\n+    """New."""\n'
        assert_that(found(patch), equal_to([]))

    def test_a_function_that_is_no_finding_module_is_not_judged(self) -> None:
        """A module with no function that has ``finding`` in its name."""
        head = {**SOURCES, MODULE: PLAIN.replace("x > 1", "x > 2")}
        assert_that(found(LOOSENED, head=head), equal_to([]))

    def test_a_module_that_does_not_parse_is_not_judged(self) -> None:
        """The head's text is what the patch changes; an unreadable one has none."""
        head = {**SOURCES, MODULE: "def findings(:\n"}
        assert_that(found(LOOSENED, head=head), equal_to([]))

    def test_a_test_module_is_not_judged(self) -> None:
        """Changing a test file needs no test."""
        patch = LOOSENED.replace(MODULE, TESTS)
        assert_that(found(patch), equal_to([]))


GRANT = (
    "## Execution\nReprieve: #480, the owner, 2026-11-14T18:29:33-08:00:"
    ' "reprieve for #480 is'
    ' granted"\n'
)


class TestReprieve(unittest.TestCase):
    """The owner's reprieve lifts the check for the PR he names (keyword: reprieve)."""

    def test_a_cited_grant_is_a_reprieve(self) -> None:
        """The accepted form: an instant, and his quoted words with the number."""
        assert_that(lintchange.reprieved(GRANT, 480), equal_to(True))

    def test_a_grant_in_a_list_item_is_a_reprieve(self) -> None:
        """The accepted form: the Execution's lines are list items."""
        body = GRANT.replace("\nReprieve", "\n- Reprieve")
        assert_that(lintchange.reprieved(body, 480), equal_to(True))

    def test_a_grant_that_is_one_input_off_is_no_reprieve(self) -> None:
        """The nearest inputs: no instant, no zone, other words, another number."""
        cases = {
            "no instant": GRANT.replace("2026-11-14T18:29:33-08:00", "yesterday"),
            "no zone": GRANT.replace("-08:00", ""),
            "other words": GRANT.replace('"reprieve for', '"go ahead for'),
            "number longer": GRANT.replace('"reprieve for #480', '"reprieve for #4800'),
            "number shorter": GRANT.replace('"reprieve for #480', '"reprieve for #48'),
            "outside the quote": (
                '## Execution\nReprieve: #480 reprieve 2026-11-14T18:29:33-08:00 "ok"\n'
            ),
            "fenced": f"## Execution\n```\n{GRANT}```\n",
        }
        for name, body in cases.items():
            with self.subTest(name):
                assert_that(lintchange.reprieved(body, 480), equal_to(False))

    def test_the_reprieve_of_one_pull_does_not_lift_another(self) -> None:
        """The grant names #480; the check at #481 still finds."""
        assert_that(lintchange.reprieved(GRANT, 481), equal_to(False))


def lint_tests(case: unittest.TestCase, body: str, pull: str) -> Sequence[str]:
    """The lint-test findings of ``plan-check`` for a loosened lint.

    Args:
        case: the test, whose end removes the repository.
        body: the PR's body.
        pull: the ``--pull`` value, or none.

    Returns:
        The findings.
    """
    repo = loosened(case)
    patch = run_git(repo.root, "diff", "-U0", "--no-renames", "origin/main")
    args = argparse.Namespace(pull=pull, body=body)
    return plancheck_commands.lint_tests(args, "", patch, repo.root)


class TestGranted(unittest.TestCase):
    """``plan-check`` finds nothing for the PR the owner granted (keyword: reprieve)."""

    def test_the_granted_pull_has_no_finding(self) -> None:
        """The accepted form."""
        assert_that(lint_tests(self, GRANT, "o/r#480"), equal_to([]))

    def test_another_pull_has_its_finding(self) -> None:
        """The nearest input: the grant is for #480, the check is of #481."""
        assert_that(lint_tests(self, GRANT, "o/r#481"), has_length(1))

    def test_no_pull_has_its_finding(self) -> None:
        """The nearest input: no --pull, so no reprieve is read."""
        assert_that(lint_tests(self, GRANT, ""), has_length(1))


def loosened(case: unittest.TestCase) -> diffrepo.Repository:
    """A repository whose main has the lint and its test, and whose branch loosens it.

    Args:
        case: the test, whose end removes the repository.

    Returns:
        The repository, at the loosened lint.
    """
    repo = diffrepo.make_repository(case)
    run_git(repo.root, "checkout", "-q", "main")
    for name, text in ((MODULE, BEFORE), (TESTS, "from .. import lint\n")):
        diffrepo.commit(repo, name, text)
    for words in (
        ("update-ref", "refs/remotes/origin/main", "HEAD"),
        ("checkout", "-q", "-B", "work"),
    ):
        run_git(repo.root, *words)
    diffrepo.commit(repo, MODULE, AFTER)
    return repo


class TestPlanCheck(unittest.TestCase):
    """``plan-check`` on a real repository."""

    def test_a_loosened_condition_with_no_new_test_is_refused(self) -> None:
        """Done-when: planted, refused, naming the module and the function."""
        done = plan_check(loosened(self), body_of("1. `rg -n x src/`\n"))
        said = [
            "lint-test: `pitboss.lint` function `findings`",
            "Lint test findings: 1",
        ]
        assert_that(refused_with(done, *said), equal_to(True))

    def test_a_new_test_the_plan_cites_is_accepted(self) -> None:
        """The accepted form."""
        repo = loosened(self)
        added = "from .. import lint\n\n\ndef test_it():\n    pass\n"
        diffrepo.commit(repo, TESTS, added)
        rows = "1. `rg -n x src/`\n2. `rg -n test_it src/`\n"
        assert_that(passed(plan_check(repo, body_of(rows))), equal_to(True))
