"""Commands with words, bare and with ``--config`` (keyword: default-config)."""

import functools
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import configsearch
from . import configcases, fakes, test_quiet, world

NOW = ("--now", world.FUTURE)
PUSH = ("--no-dry-run", "--now", test_quiet.at(16), "origin", "branch-1")
# Every ``slots`` action that takes words, each after the one it needs.
SLOTS = (
    ("set", "tiny", "agent-1", "#50", "--running", "agent-1"),
    ("heard", "tiny"),
    ("wait", "tiny"),
    ("resume", "tiny"),
    ("free", "tiny", "--done", "agent-1"),
    ("add", "extra", "small"),
    ("remove", "extra"),
    ("failed", "#3", "small"),
    ("deviation", "#7", "/nonexistent-review"),
    ("check", "2"),
)
CODES = [0, 0, 0, 0, 0, 0, 0, 0, 2, 0]


def pushed(here: world.World) -> bool:
    """Whether the world ran ``git push origin branch-1``.

    Args:
        here: the world.

    Returns:
        True when it did.
    """
    return ["git", "push", "origin", "branch-1"] in [list(c) for c in here.calls]


def deprecated(found: world.Result, command: str) -> int:
    """How many times a run said the first word is deprecated.

    Args:
        found: what the command did.
        command: the command.

    Returns:
        The count.
    """
    return found.err.count(configcases.deprecation(command))


def run_form(
    before: Sequence[str],
    after: Sequence[str],
    form: str,
    here: world.World | None = None,
) -> configcases.Ran:
    """Run a command line, with its configuration given as a form says.

    Args:
        before: the words before the configuration.
        after: the words after it.
        form: ``bare``, ``option`` or ``positional``.
        here: the world; a new one when None.

    Returns:
        The world and what the command did.
    """
    here = here or configcases.fresh()
    words = configcases.with_form(before, after, here, form)
    return configcases.Ran(here, configcases.run(here, words))


def pushing(form: str) -> configcases.Ran:
    """Run ``push`` once the quiet period is over.

    Args:
        form: ``bare``, ``option`` or ``positional``.

    Returns:
        The world and what the push did.
    """
    here, _ = run_form(("queued",), ("--now", test_quiet.at(0)), form)
    return run_form(("push",), PUSH, form, here)


def stepping(form: str) -> tuple[Sequence[Sequence[object]], str]:
    """Run every ``slots`` action with words in a new world.

    Args:
        form: ``bare``, ``option`` or ``positional``.

    Returns:
        What each action did, and the ledger at the end.
    """
    here = configcases.fresh()
    runs = [
        run_form(("slots", words[0]), (*words[1:], *NOW), form, here)[1]
        for words in SLOTS
    ]
    ledger = here.ledger.read_text().replace(str(here.workspace), "<workspace>")
    return [configcases.seen(here, each, "slots") for each in runs], ledger


class TestPush(unittest.TestCase):
    """``push`` takes git's words whichever way it is given its configuration."""

    def test_git_gets_its_words(self) -> None:
        """``push --no-dry-run origin branch-1`` runs ``git push origin branch-1``."""
        found = []
        for form in ("bare", "option", "positional"):
            here, result = pushing(form)
            found.append((pushed(here), configcases.seen(here, result, "push")))
        assert_that(found, equal_to([found[0]] * 3))
        assert_that(found[0][0], equal_to(True))


class TestNext(unittest.TestCase):
    """``next`` takes a ticket whichever way it is given its configuration."""

    def test_the_ticket_is_read(self) -> None:
        """``next #12`` is the ticket ``#12`` and ``--config`` changes nothing."""
        ran = [run_form(("next",), ("#12", *NOW), form) for form in ("bare", "option")]
        seen = [configcases.seen(here, result, "next") for here, result in ran]
        assert_that(seen[0], equal_to(seen[1]))
        assert_that(ran[0][1].out, contains_string("owner/project#12"))


class TestSlots(unittest.TestCase):
    """Every ``slots`` action with words reads them whichever way it is given."""

    def test_each_action_with_its_words(self) -> None:
        """Bare, with ``--config`` and with the old word: same results, same ledger."""
        outcomes = [stepping(form) for form in ("bare", "option", "positional")]
        assert_that(outcomes, equal_to([outcomes[0]] * 3))
        assert_that([each[-1] for each in outcomes[0][0]], equal_to(CODES))


class TestOverlap(unittest.TestCase):
    """The old first word works for one version, with the deprecation line."""

    def test_push_with_a_toml_first_word(self) -> None:
        """``push CONFIG origin branch-1`` still pushes, and says it is deprecated."""
        here, result = pushing("positional")
        assert_that((pushed(here), deprecated(result, "push")), equal_to((True, 1)))

    def test_the_first_word_of_slots_check(self) -> None:
        """``slots check`` reads a ``.toml`` or a named file as the configuration."""
        here = configcases.fresh()
        inside = here.workspace.joinpath(*configsearch.CONFIG_DIRECTORY)
        configcases.copy_config(here, inside / "project.toml")
        words = {"CONFIG 2": [here.config, "2"], "project": ["project"], "2": ["2"]}
        found = {
            name: configcases.run(here, ["slots", "check", *each, *NOW])
            for name, each in words.items()
        }
        said = {name: deprecated(each, "slots") for name, each in found.items()}
        codes = {name: each.code for name, each in found.items()}
        assert_that(said, equal_to({"CONFIG 2": 1, "project": 1, "2": 0}))
        assert_that(codes, equal_to({"CONFIG 2": 0, "project": 0, "2": 0}))

    def test_a_word_that_cannot_go_anywhere_is_the_old_configuration(self) -> None:
        """``clean foo`` has no other word to give ``foo`` to: it is the old name."""
        here = configcases.placed(configcases.cleaning, configcases.SEARCHED)
        running = functools.partial(configcases.run, here, ["clean", "foo", *NOW])
        assert_that(fakes.error_of(running), contains_string("no foo.toml"))

    def test_an_extra_word_after_the_option_is_refused(self) -> None:
        """``clean --config C foo`` and ``review-form --config C a b`` exit 2."""
        here = configcases.fresh()
        refused = {"clean": ["foo"], "review-form": ["a", "b"]}
        found = {
            name: configcases.run(here, [name, "--config", here.config, *words])
            for name, words in refused.items()
        }
        assert_that(
            {k: v.code for k, v in found.items()},
            equal_to({"clean": 2, "review-form": 2}),
        )
        assert_that(
            all("unexpected argument" in v.err for v in found.values()), equal_to(True)
        )
