"""A project whose config needs no drafts gets none (keyword: no-drafts, pitboss#216)."""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import briefconfig, draftrule
from ..brief import Kind
from . import quietworld, world
from .briefmake import has_all, has_none, text
from .linting import lint, write_text
from .test_brief_workers import PLAIN
from .test_forms import PROJECT, outcome
from .test_quiet import at, clear_world

READY_HELD = dataclasses.replace(PLAIN, holds=True)
DRAFTED = briefconfig.Brief(drafts=True, holds=True, worker_lines=(), review_lines=())
NO_DRAFTS = PROJECT + "[slots.brief]\ndrafts = false\n"
DRAFTS = PROJECT + "[slots.brief]\ndrafts = true\n"
APPENDED = "Open the PR as a draft until its Plan is approved.\n"
PUSH_NO_DRAFTS = (
    "Push: push with `uvx pitboss push proj --no-dry-run` (without `--draft`:"
    " this project's PRs are not drafts, and push refuses `--draft` here)"
)
PUSH_DRAFTS = "(add `--draft` for a draft PR)"


class TestNoDraftsBrief(unittest.TestCase):
    """The generated brief says the setting's side."""

    def test_a_project_without_drafts_opens_ready_and_pushes_without_draft(
        self,
    ) -> None:
        """Ready, the push line without --draft, and no draft instruction."""
        found = text(Kind.NEW_PR, project=READY_HELD)
        has_all(found, ["Ready: this project's PRs are not drafts", PUSH_NO_DRAFTS])
        has_none(found, ["Draft: open the PR as a draft", PUSH_DRAFTS])

    def test_a_project_with_drafts_opens_a_draft_and_may_push_one(self) -> None:
        """The opposite: Draft, and the push line that adds --draft."""
        found = text(Kind.NEW_PR, project=DRAFTED)
        has_all(found, ["Draft: open the PR as a draft", PUSH_DRAFTS])
        has_none(found, ["Ready: this project's PRs are not drafts", PUSH_NO_DRAFTS])

    def test_the_generated_brief_passes_its_own_rule(self) -> None:
        """The sentences of a no-drafts brief are not draft instructions."""
        found = text(Kind.NEW_PR, project=READY_HELD)
        assert_that(draftrule.findings("brief", found), equal_to([]))


class TestNoDraftsPush(unittest.TestCase):
    """``push --draft`` is refused where the config says no drafts."""

    def push(self, setting: str, *options: str) -> tuple[int, str, list[list[str]]]:
        """Push in a world whose config has ``setting``.

        Args:
            setting: the text put before the ``[runners]`` table.
            *options: the options of ``push``.

        Returns:
            The exit code, the output and the git pushes that ran.
        """
        here = clear_world()
        quietworld.edit_config(here, "[runners]", f"{setting}[runners]")
        world.again(here, "queued", "--now", at(0))
        ran = world.again(here, "push", "--now", at(16), "--no-dry-run", *options)
        pushed = [list(c) for c in here.calls if list(c[:2]) == ["git", "push"]]
        return ran.code, ran.out, pushed

    def test_draft_is_refused_naming_the_setting(self) -> None:
        """Exit 1, the setting named, and git is not run."""
        code, out, pushed = self.push("[slots.brief]\ndrafts = false\n\n", "--draft")
        assert_that((code, pushed), equal_to((1, [])))
        assert_that(out, contains_string("[slots.brief] drafts = false"))

    def test_draft_goes_out_where_drafts_are_the_default(self) -> None:
        """Without the setting a draft push works as before."""
        code, _, pushed = self.push("", "--draft")
        assert_that((code, len(pushed)), equal_to((0, 1)))

    def test_a_ready_push_goes_out_where_drafts_are_off(self) -> None:
        """Only --draft is refused."""
        code, _, pushed = self.push("[slots.brief]\ndrafts = false\n\n")
        assert_that((code, len(pushed)), equal_to((0, 1)))


class TestNoDraftsLint(unittest.TestCase):
    """``lint brief`` refuses a sentence that tells the worker to open a draft."""

    def test_an_appended_draft_sentence_is_refused(self) -> None:
        """Refused where drafts are off, accepted where they are on."""
        off = write_text("off.toml", NO_DRAFTS)
        on = write_text("on.toml", DRAFTS)
        found = [
            outcome("brief", APPENDED, "--config", off),
            outcome("brief", APPENDED, "--config", on),
            outcome("brief", APPENDED),
            outcome("brief", "Open the PR ready.\n", "--config", off),
            outcome("brief", "Push with `--draft` for a draft.\n", "--config", off),
            outcome("brief", "Do not open the PR as a draft.\n", "--config", off),
        ]
        expected = [
            (1, "(no-drafts)"),
            (0, "ok"),
            (0, "ok"),
            (0, "ok"),
            (1, "(no-drafts)"),
            (0, "ok"),
        ]
        assert_that(found, equal_to(expected))

    def test_the_finding_names_the_setting(self) -> None:
        """The message says where the rule is set."""
        off = write_text("off2.toml", NO_DRAFTS)
        ran = lint("brief", write_text("a.md", APPENDED), "--config", off)
        assert_that(ran.out, contains_string("[slots.brief] drafts = false"))

    def test_a_bad_config_is_a_usage_error(self) -> None:
        """A table of the wrong type is 2."""
        bad = write_text("bad.toml", PROJECT + "[slots.brief]\ndrafts = 1\n")
        ran = lint("brief", write_text("b.md", "x\n"), "--config", bad)
        assert_that(ran.code, equal_to(2))
