"""A worker brief states the standing rules and the environment.

The keyword is env-check, quire#1065.

The rules are read from ``standing.tsv`` and not retyped here: each row's needle must
be in the printed brief of every worker kind, for each kind of repository.
"""

import argparse
import pathlib
import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length, is_

from .. import brief, envcheck_commands, envrules
from . import fakes, world
from .briefmake import text as brief_text
from .test_gate_run import Fake

SLUGS = (
    "bats-lang/bats",
    "bats-lang/quire",
    "bats-lang/pwa",
    "dev-skill-up/pitboss",
    "o/r",
)
WORKERS = tuple(
    each
    for each in brief.Kind
    if "Hand-back:" in brief_text(each) and "Finish inside the turn" in brief_text(each)
)
SOURCES = pathlib.Path(__file__).parent.parent


class TestStanding(unittest.TestCase):
    """Every row of the register is in the printed brief."""

    def test_c35_there_are_worker_kinds(self) -> None:
        """The loop below runs over something."""
        assert_that(len(WORKERS) > 3, is_(True))

    def test_c35_each_rule_is_in_each_worker_brief_of_each_repository_kind(
        self,
    ) -> None:
        """Generated from the register, per repository kind."""
        for slug in SLUGS:
            for kind in WORKERS:
                printed = brief_text(kind, repo=slug)
                for rule in envrules.needles(slug):
                    assert_that(
                        printed,
                        contains_string(rule.needle),
                        f"{slug} {kind} {rule.topic}",
                    )

    def test_c35_a_rule_of_another_kind_is_not_printed(self) -> None:
        """The compiler is for bats-lang repositories, the venv for pitboss."""
        kind = WORKERS[0]
        assert_that("bootstrap/c" in brief_text(kind, repo="o/r"), is_(False))
        assert_that("bootstrap/c" in brief_text(kind, repo="bats-lang/bats"), is_(True))
        assert_that(".venv" in brief_text(kind, repo="dev-skill-up/pitboss"), is_(True))

    def test_c35_the_long_check_limit_is_one_constant(self) -> None:
        """No brief module writes the number: it is read from ``envrules``."""
        for path in SOURCES.glob("brief*.py"):
            assert_that(
                str(envrules.LONG_CHECK_SECONDS) in path.read_text("utf-8"),
                is_(False),
                path.name,
            )
        printed = brief_text(WORKERS[0], repo="bats-lang/bats")
        assert_that(printed, contains_string(f"timeout {envrules.LONG_CHECK_SECONDS}"))
        assert_that(
            printed, contains_string(f"more than {envrules.LONG_CHECK_SECONDS} seconds")
        )


class TestEnvCheck(unittest.TestCase):
    """The pre-flight command and the refusal of a give-up without it."""

    def verdicts(self, runner: Fake, slug: str) -> list[str]:
        """The lines of ``env-check`` for a repository with a runner.

        Args:
            runner: the fake.
            slug: the repository.

        Returns:
            The lines.
        """
        args = argparse.Namespace(safe_run=runner, repo=fakes.directory())
        return list(
            envcheck_commands.verdicts(args, envrules.NEEDS, envrules.kinds_of(slug))
        )

    def test_c35_the_command_reads_its_configuration(self) -> None:
        """The configuration's repository needs nothing here: ``env: ok``, exit 0."""
        here = world.make_world()
        done = world.invoke(here, "env-check", "--config", here.config)
        assert_that((done.code, done.out), equal_to((0, f"{envrules.OK_LINE}\n")))

    def test_c35_a_missing_compiler_is_named_with_the_command_to_get_it(self) -> None:
        """No bats on PATH: the line names it and the build from bootstrap/c."""
        lines = self.verdicts(Fake(status=1, out=""), "bats-lang/bats")
        assert_that(lines, has_length(1))
        assert_that(lines[0], contains_string("missing bats"))
        assert_that(lines[0], contains_string("make -C /tmp/seed debug/bats"))

    def test_c35_a_present_tool_is_ok_and_other_repositories_need_nothing(self) -> None:
        """The check passes, or the kind needs nothing."""
        assert_that(
            self.verdicts(Fake(out="/usr/bin/bats\n"), "bats-lang/bats"), equal_to([])
        )
        assert_that(self.verdicts(Fake(status=1), "o/r"), equal_to([]))

    def test_c35_giving_up_for_a_missing_tool_needs_the_env_check_output(self) -> None:
        """Refused without the lines, accepted with a missing line, refused with ok."""
        gave_up = "NOT STARTED: no `bats` on PATH\nDeviations: none\n"
        assert_that(envrules.give_up_refusal(gave_up), contains_string("env-check"))
        missing = gave_up + "env: missing bats: no `bats` on PATH; get it with: x\n"
        assert_that(envrules.give_up_refusal(missing), equal_to(""))
        said_ok = gave_up + "env: ok\n"
        assert_that(
            envrules.give_up_refusal(said_ok), contains_string("printed `env: ok`")
        )
        assert_that(envrules.give_up_refusal("Deviations: none\n"), equal_to(""))
