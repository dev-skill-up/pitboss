"""The Plan digest covers an expanded block as its command (pitboss#358, #399)."""

import unittest

from hamcrest import assert_that, equal_to, is_not

from .. import bodydigest, expansion, plandigest, planrow
from .linting import block as run

PROSE = "1. Run `git rev-parse HEAD`.\n2. Run `make test`.\n"
DISPOSITION = "src/a.py:3: edited\n"
COMMANDS = ["$ git rev-parse HEAD", "$ make test"]


def plan(first: str = "abc\n", second: str = "ok\n", prose: str = PROSE) -> str:
    """A body whose Plan section holds two expanded blocks.

    Args:
        first: what the first command printed.
        second: what the second printed.
        prose: the Plan's prose.

    Returns:
        The body.
    """
    return (
        f"## Plan\n{prose}{DISPOSITION}\n{run('git rev-parse HEAD', first)}"
        f"{run('make test', second)}\n## Execution\nthe work\n"
    )


def digest(body: str) -> str:
    """The digest of the Plan section of a body.

    Args:
        body: the PR body.

    Returns:
        The digest.
    """
    return expansion.section_digest(plandigest.section(body))


class TestTheDigestCollapsesExpandedBlocks(unittest.TestCase):
    """What changes the digest and what does not."""

    def test_re_expanding_at_a_new_head_keeps_the_digest(self) -> None:
        """Another head and another timing line are the same Plan."""
        again = plan("def\n", "Installed 7 packages in 9ms\nok\n")
        assert_that(digest(again), equal_to(digest(plan())))

    def test_the_collapsed_section_has_the_command_lines_only(self) -> None:
        """Each block is its `$ command` line."""
        collapsed = expansion.collapsed(plandigest.section(plan()))
        assert_that(collapsed.splitlines()[-2:], equal_to(COMMANDS))

    def test_each_edit_of_the_plan_changes_the_digest(self) -> None:
        """Command, prose, disposition, an added and a removed block."""
        base = digest(plan())
        other_command = plan().replace("make test", "make lint")
        other_prose = plan(prose=PROSE.replace("Run", "Execute"))
        other_line = plan().replace("edited", "not edited, a reason")
        added = plan().replace("\n## Execution", run("ls", "x\n") + "\n## Execution")
        removed = plan().replace(run("make test", "ok\n"), "")
        for body in (other_command, other_prose, other_line, added, removed):
            with self.subTest(body):
                assert_that(digest(body), is_not(equal_to(base)))

    def test_a_hand_edited_block_stays_in_and_changes_the_digest(self) -> None:
        """The nearest input: the contents changed, the header kept."""
        edited = plan().replace("abc\n", "forged output\n")
        assert_that(digest(edited), is_not(equal_to(digest(plan()))))
        assert_that(
            "forged output" in expansion.collapsed(plandigest.section(edited)),
            equal_to(True),
        )

    def test_a_block_with_no_closing_fence_stays_in(self) -> None:
        """An unclosed block is not collapsed."""
        text = run("make test", "ok\n").rstrip("\n").rsplit("\n", 1)[0] + "\n"
        assert_that(expansion.collapsed(text), equal_to(text))

    def test_a_block_that_does_not_start_with_a_command_stays_in(self) -> None:
        """A header over contents with no `$ ` first line is not an expansion."""
        contents = "no command\n"
        text = f"```{expansion.info(contents)}\n{contents}```"
        assert_that(expansion.collapsed(text), equal_to(text))


def legacy_digest(body: str) -> str:
    """The digest the Plan section had before the blocks were collapsed.

    Args:
        body: the PR body.

    Returns:
        The digest.
    """
    return expansion.text_digest(plandigest.section(body))


class TestTheOldDigestIsNoLongerAccepted(unittest.TestCase):
    """The digest before the collapse is dropped (pitboss#399)."""

    def test_the_old_digest_is_not_the_new_one(self) -> None:
        """The two are told apart, so the acceptance is a real overlap."""
        assert_that(legacy_digest(plan()), is_not(equal_to(digest(plan()))))

    def test_the_text_digest_is_the_body_digest(self) -> None:
        """The two modules each hold the code (no import between them)."""
        for text in ("a\r\nb\n\n", "plain", "", "x  \n"):
            with self.subTest(text):
                assert_that(
                    expansion.text_digest(text), equal_to(bodydigest.digest(text))
                )

    def test_the_section_changed_reads_the_collapsed_digest_alone(self) -> None:
        """The collapsed digest is the section; the old one and another are not."""
        section = plandigest.section(plan())
        assert_that(expansion.section_changed(digest(plan()), section), equal_to(False))
        for given in (legacy_digest(plan()), "0" * 16):
            assert_that(expansion.section_changed(given, section), equal_to(True))

    def test_an_approved_old_digest_no_longer_exempts_the_plan_rows(self) -> None:
        """The Plan-row rule judges a Plan whose old digest was approved."""
        body = plan() + "\n## Evidence\n" + run("other", "x\n")
        assert_that(
            planrow.findings("b", body, [legacy_digest(body)]), is_not(equal_to([]))
        )
        assert_that(planrow.findings("b", body, ["0" * 16]), is_not(equal_to([])))
