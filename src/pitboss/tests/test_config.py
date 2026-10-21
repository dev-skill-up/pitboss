"""Tests for reading the configuration."""

import pathlib
import tempfile
import unittest

from hamcrest import assert_that, calling, contains_exactly, equal_to, raises

from .. import config
from . import fakes


class TestLoad(unittest.TestCase):
    """Loading a configuration file."""

    def setUp(self) -> None:
        """Make a workspace."""
        self.directory = pathlib.Path(tempfile.mkdtemp())

    def test_defaults(self) -> None:
        """Only the project is required; everything else has a default."""
        settings = fakes.settings(self.directory)
        assert_that(settings.project.base_branch, equal_to("main"))
        assert_that(settings.libraries, equal_to(()))
        assert_that(
            [repo.slug for repo in settings.runners], contains_exactly("owner/project")
        )
        assert_that(settings.timeout_minutes, equal_to(60))
        assert_that(settings.idle_hours, equal_to(3.0))
        assert_that(settings.slots.models, equal_to(()))
        assert_that(settings.slots.default, equal_to(()))
        assert_that(
            settings.slots.ledger,
            equal_to(self.directory / "project" / ".git" / "pitboss-slots.json"),
        )
        assert_that(settings.review.gated_form, equal_to(settings.review.form))
        assert_that(settings.reminders, equal_to(config.DEFAULT_REMINDERS))

    def test_everything(self) -> None:
        """Every key is read."""
        settings = fakes.settings(
            self.directory,
            "[libraries]\n"
            'repositories = ["lib", "other/elsewhere"]\n'
            'no_auto_merge = ["lib"]\n'
            "[runners]\n"
            'repositories = ["project"]\n'
            "[review]\n"
            'gated = ["lib"]\n'
            'trusted_associations = ["OWNER"]\n'
            "[review.form]\n"
            'lines = ["Review of {sha}: {verdict}"]\n'
            'approved = "yes"\n'
            "[merge_queue]\n"
            "timeout_minutes = 30\n"
            "[worktrees]\n"
            "idle_hours = 1.5\n"
            "[sweep]\n"
            'reminders = ["one"]\n'
            "[slots]\n"
            'ledger = "/somewhere/ledger.json"\n'
            'models = ["small", "large"]\n'
            'priority_labels = ["urgent"]\n'
            'default = [{name = "first", model = "small"}]\n'
            "[slots.model_labels]\n"
            'hard = "large"\n',
        )
        assert_that(
            [repo.slug for repo in settings.libraries],
            contains_exactly("owner/lib", "other/elsewhere"),
        )
        assert_that(settings.no_auto_merge, equal_to(frozenset({"owner/lib"})))
        assert_that([repo.slug for repo in settings.runners], equal_to(["owner/project"]))
        assert_that(settings.review.gated, equal_to(frozenset({"owner/lib"})))
        assert_that(settings.review.trusted, equal_to(frozenset({"OWNER"})))
        assert_that(settings.review.form.approved, equal_to("yes"))
        assert_that(settings.review.gated_form.approved, equal_to("yes"))
        assert_that(settings.timeout_minutes, equal_to(30))
        assert_that(settings.idle_hours, equal_to(1.5))
        assert_that(settings.reminders, equal_to(("one",)))
        assert_that(settings.slots.ledger, equal_to(pathlib.Path("/somewhere/ledger.json")))
        assert_that(settings.slots.model_labels, equal_to({"hard": "large"}))
        assert_that(
            settings.slots.default,
            contains_exactly(config.SlotSpec(name="first", model="small")),
        )
        assert_that(
            [repo.slug for repo in settings.repositories],
            contains_exactly("owner/project", "owner/lib", "other/elsewhere"),
        )

    def test_wrong_types(self) -> None:
        """A key of the wrong type is an error that names it."""
        for extra, word in [
            ('libraries = "lib"\n', r"\[libraries\]"),
            ('[libraries]\nrepositories = "lib"\n', "repositories"),
            ('[slots]\ndefault = "slot"\n', "slots.default"),
        ]:
            path = self.directory / "wrong.toml"
            path.write_text(
                extra + "[project]\nowner = 'o'\nrepository = 'r'\nmain_clone = '/c'\n"
            )
            assert_that(
                calling(config.load).with_args(str(path), self.directory),
                raises(ValueError, word),
            )


class TestLocate(unittest.TestCase):
    """Finding the file a name stands for."""

    def test_name_in_a_parent(self) -> None:
        """A name is looked up in .claude/pitboss of the directory or a parent."""
        directory = pathlib.Path(tempfile.mkdtemp())
        target = directory / ".claude" / "pitboss" / "mine.toml"
        target.parent.mkdir(parents=True)
        target.write_text("")
        inner = directory / "a" / "b"
        inner.mkdir(parents=True)
        assert_that(config.locate("mine", inner), equal_to(target))

    def test_path(self) -> None:
        """A path is taken as it is."""
        start = pathlib.Path("/nowhere")
        assert_that(
            config.locate("x/y.toml", start), equal_to(pathlib.Path("x/y.toml"))
        )
        assert_that(config.locate("y.toml", start), equal_to(pathlib.Path("y.toml")))

    def test_missing(self) -> None:
        """A name with no file is an error."""
        directory = pathlib.Path(tempfile.mkdtemp())
        assert_that(
            calling(config.locate).with_args("absent", directory),
            raises(FileNotFoundError, "absent.toml"),
        )
