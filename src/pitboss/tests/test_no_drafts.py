"""A project whose config needs no drafts gets none (keyword: no-drafts, #216)."""

import dataclasses
import pathlib
import tomllib
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import briefconfig, draftrule, exempt
from ..brief import Kind
from . import quietworld, world
from .briefmake import PROJECT as DRAFTED
from .briefmake import text
from .says import has_all, has_none, says
from .linting import lint, write_text
from .test_brief_workers import PLAIN
from .test_quiet import at, clear_world
from .pushworld import elsewhere

PROJECT = "[project]\nowner = 'o'\nrepository = 'r'\nmain_clone = '/c'\n"

READY_HELD = dataclasses.replace(PLAIN, holds=True)
OFF_CONFIG = PROJECT + "[slots.brief]\ndrafts = false\n"
ON_CONFIG = PROJECT + "[slots.brief]\ndrafts = true\n"
APPENDED = "Open the PR as a draft until its Plan is approved.\n"
OFF = "[slots.brief] drafts = false"
PUSH_NO_DRAFTS = (
    "Push: push with `uvx pitboss push proj --no-dry-run` (without `--draft`:"
    " this project's PRs are not drafts, and push refuses `--draft` here)"
)
PUSH_DRAFTS = "(add `--draft` for a draft PR)"
READY = "Ready: this project's PRs are not drafts"
DRAFT = "Draft: open the PR as a draft"


def pushed_with(setting: str, *options: str) -> tuple[object, str, int]:
    """Push in a world whose config has ``setting``.

    Args:
        setting: the text put before the ``[runners]`` table.
        *options: the options of ``push``.

    Returns:
        The exit code, the output and how many git pushes ran.
    """
    here = clear_world()
    quietworld.edit_config(here, "[runners]", f"{setting}[runners]")
    world.again(here, "queued", "--now", at(0))
    ran = world.again(here, "push", "--now", at(16), "--no-dry-run", *options)
    return ran.code, ran.out, sum(list(c[:2]) == ["git", "push"] for c in here.calls)


def outcome(kind: str, body: str, *options: str) -> tuple[object, str]:
    """Run ``pitboss lint`` on a text.

    Args:
        kind: the kind of check.
        body: the text.
        *options: the options after the file.

    Returns:
        The exit code, and the last word of the first line printed.
    """
    ran = lint(kind, write_text("text.md", body), *options)
    return ran.code, (ran.out + ran.err).split()[-1]


def brief_outcomes(config: str, bodies: Sequence[str]) -> Sequence[object]:
    """What ``lint brief`` says to each body under a config.

    Args:
        config: the config's path.
        bodies: the texts.

    Returns:
        The exit code and the check named, for each.
    """
    return [outcome("brief", each, "--config", config) for each in bodies]


class TestNoDraftsBrief(unittest.TestCase):
    """The generated brief says the setting's side."""

    def test_the_brief_follows_the_setting(self) -> None:
        """Ready and a push without --draft, or the opposite."""
        off = text(Kind.NEW_PR, project=READY_HELD)
        on = text(Kind.NEW_PR, project=DRAFTED)
        has_all(off, [READY, PUSH_NO_DRAFTS])
        has_none(off, [DRAFT, PUSH_DRAFTS])
        has_all(on, [DRAFT, PUSH_DRAFTS])
        has_none(on, [READY, PUSH_NO_DRAFTS])
        # the sentences of a no-drafts brief are not draft instructions
        assert_that(draftrule.findings("brief", off), equal_to([]))


class TestNoDraftsPush(unittest.TestCase):
    """``push --draft`` is refused where the config says no drafts."""

    def test_draft_is_refused_naming_the_setting(self) -> None:
        """Exit 1, the setting named and git not run; other pushes go out."""
        setting = "[slots.brief]\ndrafts = false\n\n"
        refused = pushed_with(setting, "--draft")
        others = [pushed_with("", "--draft"), pushed_with(setting)]
        assert_that((refused[0], refused[2]), equal_to((1, 0)))
        assert_that(refused[1], contains_string(OFF))
        assert_that([(each[0], each[2]) for each in others], equal_to([(0, 1)] * 2))


class TestPitbossHasNoDrafts(unittest.TestCase):
    """Pitboss's own PRs are never drafts, whatever the configuration says (B19)."""

    def test_b19_a_draft_push_to_pitboss_is_refused_with_no_setting(self) -> None:
        """The remote names dev-skill-up/pitboss; the config says nothing of drafts."""
        here = clear_world()
        url = "git@github.com:dev-skill-up/pitboss.git"
        elsewhere(here, url)
        argv = ["push", "--now", at(1), "--no-dry-run", "--draft"]
        refused = world.again(here, *argv, "elsewhere", "branch-1")
        ran = sum(list(c[:2]) == ["git", "push"] for c in here.calls)
        assert_that((refused.code, ran), equal_to((1, 0)))
        says(refused.out, "dev-skill-up/pitboss")

    def test_b19_only_pitboss_and_the_listed_repositories_have_no_drafts(self) -> None:
        """The rule for a slug: pitboss, a listed one, and no other."""
        here = clear_world()
        start = pathlib.Path(here.workspace)
        found = [
            draftrule.drafts_off(here.config, start, slug)
            for slug in ("dev-skill-up/pitboss", "owner/project", None)
        ]
        assert_that(found, equal_to([True, False, False]))
        assert_that(draftrule.REFUSAL, contains_string("dev-skill-up/pitboss"))

    def test_b19_the_sweep_reads_a_pitboss_pr_as_never_a_draft(self) -> None:
        """The project's ``no_drafts`` holds pitboss whatever the file lists."""
        text = PROJECT + "[slots.brief]\ndrafts = true\n"
        document = tomllib.loads(text)
        listed = exempt.slugs(briefconfig.from_document(document).no_drafts, "o")
        assert_that(exempt.PITBOSS in listed, equal_to(True))


class TestNoDraftsLint(unittest.TestCase):
    """``lint brief`` refuses a sentence that tells the worker to open a draft."""

    def test_an_appended_draft_sentence_is_refused(self) -> None:
        """Refused where drafts are off, accepted where they are on."""
        bodies = [
            APPENDED,
            "Open the PR ready.\n",
            "Push with `--draft` for a draft.\n",
            "Do not open the PR as a draft.\n",
        ]
        found = [
            brief_outcomes(write_text("off.toml", OFF_CONFIG), bodies),
            brief_outcomes(write_text("on.toml", ON_CONFIG), bodies[:1]),
            [outcome("brief", APPENDED)],
        ]
        refused, ok = (1, "(no-drafts)"), (0, "ok")
        expected = [[refused, ok, refused, ok], [ok], [ok]]
        assert_that(found, equal_to(expected))

    def test_the_finding_names_the_setting_and_a_bad_config_is_2(self) -> None:
        """The message says where the rule is set; a wrong table is a usage error."""
        off = write_text("off2.toml", OFF_CONFIG)
        bad = write_text("bad.toml", PROJECT + "[slots.brief]\ndrafts = 1\n")
        text_file = write_text("a.md", APPENDED)
        ran = [lint("brief", text_file, "--config", each) for each in (off, bad)]
        says(ran[0].out, OFF)
        assert_that(ran[1].code, equal_to(2))
