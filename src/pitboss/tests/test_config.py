"""Tests for reading the configuration."""

import functools
import pathlib
import unittest
from typing import Iterable, Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import config, configfile
from . import fakes

EVERYTHING = """
[libraries]
repositories = ["lib", "other/elsewhere"]
no_auto_merge = ["lib"]
[runners]
repositories = ["project"]
record = "/somewhere/pressure.log"
quiet_minutes = 7
[review]
gated = ["lib"]
trusted_associations = ["OWNER"]
[review.form]
lines = ["Review of {sha}: {verdict}"]
approved = "yes"
[lint.pr_body]
footers = ["made by me"]
[lint.brief]
required = ["Overlap:"]
[merge_queue]
timeout_minutes = 30
[worktrees]
idle_hours = 1.5
[sweep]
reminders = ["one"]
[slots]
ledger = "/somewhere/ledger.json"
models = ["small", "large"]
priority_labels = ["urgent"]
default = [{name = "first", model = "small"}]
[slots.model_labels]
hard = "large"
"""


def _slugs(repos: Iterable[config.Repo]) -> Sequence[str]:
    return [repo.slug for repo in repos]


def _summary(settings: config.Config) -> dict[str, object]:
    return {
        "libraries": _slugs(settings.libraries),
        "runners": _slugs(settings.runners.repositories),
        "repositories": _slugs(config.repositories(settings)),
        "no_auto_merge": settings.no_auto_merge,
        "gated": settings.review.gated,
        "trusted": settings.review.trusted,
        "approved": (
            settings.review.form.approved,
            settings.review.gated_form.approved,
        ),
        "lint": (settings.lint.footers, settings.lint.brief_lines),
        "numbers": (settings.timeout_minutes, settings.idle_hours),
        "reminders": settings.reminders,
        "slots": (
            settings.slots.models,
            settings.slots.priority_labels,
            settings.slots.default,
            settings.slots.model_labels,
        ),
    }


DEFAULTS: Mapping[str, object] = {
    "libraries": [],
    "runners": ["owner/project"],
    "repositories": ["owner/project"],
    "no_auto_merge": frozenset(),
    "gated": frozenset(),
    "trusted": frozenset(config.DEFAULT_ASSOCIATIONS),
    "approved": ("approved", "approved"),
    "lint": (config.DEFAULT_FOOTERS, ()),
    "numbers": (60, 3.0),
    "reminders": config.DEFAULT_REMINDERS,
    "slots": ((), (), (), {}),
}
READ: Mapping[str, object] = {
    "libraries": ["owner/lib", "other/elsewhere"],
    "runners": ["owner/project"],
    "repositories": ["owner/project", "owner/lib", "other/elsewhere"],
    "no_auto_merge": frozenset({"owner/lib"}),
    "gated": frozenset({"owner/lib"}),
    "trusted": frozenset({"OWNER"}),
    "approved": ("yes", "yes"),
    "lint": (("made by me",), ("Overlap:",)),
    "numbers": (30, 1.5),
    "reminders": ("one",),
    "slots": (
        ("small", "large"),
        ("urgent",),
        (config.SlotSpec(name="first", model="small"),),
        {"hard": "large"},
    ),
}
PROJECT = "[project]\nowner = 'o'\nrepository = 'r'\nmain_clone = '/c'\n"
WRONG = [
    ('libraries = "lib"\n', "[libraries]"),
    ('[libraries]\nrepositories = "lib"\n', "repositories"),
    ('[slots]\ndefault = "slot"\n', "slots.default"),
    ("[runners]\nquiet_minutes = -1\n", "quiet_minutes"),
]


def error_with(extra: str) -> str:
    """The error a configuration with ``extra`` before its project raises.

    Args:
        extra: the TOML.

    Returns:
        The error's message.
    """
    directory = fakes.directory()
    path = directory / "wrong.toml"
    path.write_text(extra + PROJECT)
    return fakes.error_of(lambda: configfile.load(str(path), directory))


class TestLoad(unittest.TestCase):
    """Loading a configuration file."""

    def test_defaults(self) -> None:
        """Only the project is required; everything else has a default."""
        directory = fakes.directory()
        settings = fakes.settings(directory)
        ledger = directory / "project" / ".git" / "pitboss-slots.json"
        found = (
            _summary(settings),
            settings.slots.ledger,
            settings.project.base_branch,
        )
        assert_that(found, equal_to((DEFAULTS, ledger, "main")))

    def test_everything(self) -> None:
        """Every key is read."""
        settings = fakes.settings(fakes.directory(), EVERYTHING)
        found = (_summary(settings), settings.slots.ledger)
        ledger = pathlib.Path("/somewhere/ledger.json")
        assert_that(found, equal_to((READ, ledger)))

    def test_wrong_types(self) -> None:
        """A key of the wrong type is an error that names it."""
        found = [word in error_with(extra) for extra, word in WRONG]
        assert_that(found, equal_to([True] * len(WRONG)))


EXAMPLE = pathlib.Path(__file__).resolve().parents[3] / "doc" / "example.toml"


class TestExample(unittest.TestCase):
    """The example configuration in the documentation."""

    def test_example_loads(self) -> None:
        """It parses, and what it gates and merges by hand are its libraries."""
        settings = configfile.load(str(EXAMPLE), EXAMPLE.parent)
        libraries = set(_slugs(settings.libraries))
        found = (
            settings.review.gated <= libraries,
            settings.no_auto_merge <= libraries,
        )
        assert_that(found, equal_to((True, True)))


class TestLocate(unittest.TestCase):
    """Finding the file a name stands for."""

    def test_lookups(self) -> None:
        """A name is looked up upwards; a path is taken as it is; none is an error."""
        directory = fakes.directory()
        target = directory / ".claude" / "pitboss" / "mine.toml"
        target.parent.mkdir(parents=True)
        target.write_text("")
        inner = directory / "a" / "b"
        inner.mkdir(parents=True)
        found = [
            configfile.locate("mine", inner),
            configfile.locate("x/y.toml", inner),
            configfile.locate("y.toml", inner),
        ]
        expected = [target, pathlib.Path("x/y.toml"), pathlib.Path("y.toml")]
        assert_that(found, equal_to(expected))
        errors = [
            fakes.error_of(functools.partial(configfile.locate, name, inner))
            for name in ("absent", "mine")
        ]
        absent = f"no absent.toml in .claude/pitboss of {inner} or its parents"
        assert_that(errors, equal_to([absent, ""]))
