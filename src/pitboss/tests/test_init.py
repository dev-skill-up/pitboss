"""Smoke tests for the pitboss package."""

import unittest
from hamcrest import assert_that, contains_string

from .. import __version__


class TestInit(unittest.TestCase):
    """Check that package-level attributes are wired up."""

    def test_version(self) -> None:
        """The package exposes a dotted version string."""
        assert_that(__version__, contains_string("."))
