"""P13.1 refuses a module that takes the configuration's repository, however reached."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import proofsource, repoproofs

READS = {
    "chain": "def f(settings):\n    return settings.project.repo.slug\n",
    "a name the project was bound to": (
        "def f(settings):\n    held = settings.project\n    return held.repo.slug\n"
    ),
    "a name the repository was bound to": (
        "def f(settings):\n    repo = settings.project.repo\n    return repo.slug\n"
    ),
    "a parameter typed Project": (
        "def f(owner: config.Project):\n    return owner.repo.slug\n"
    ),
}


def found(name: str, text: str) -> Sequence[str]:
    """What P13.1 says of a package of one module.

    Args:
        name: the module's name.
        text: its text.

    Returns:
        The findings.
    """
    package = proofsource.of_texts({f"src/pitboss/{name}.py": text})
    return list(repoproofs.configuration_repository_is_the_project_own(package))


class TestOwnRepository(unittest.TestCase):
    """What a module that is not the project's own may not take."""

    def test_every_way_to_reach_the_project_is_refused(self) -> None:
        """A chain, a bound project, a bound repository, a typed parameter."""
        for how, text in READS.items():
            with self.subTest(how):
                said = found("reader", text)
                assert_that(said, has_length(1))
                assert_that(said[0], contains_string("pitboss.reader:"))

    def test_a_module_of_the_project_own_is_not(self) -> None:
        """The modules that mean the project's own repository."""
        assert_that(found("deadscan", READS["chain"]), equal_to([]))

    def test_a_pull_request_repository_is_not_the_configuration(self) -> None:
        """A ``pull.repo`` is the PR's own."""
        text = "def f(pull):\n    return pull.repo.slug\n"
        assert_that(found("reader", text), equal_to([]))
