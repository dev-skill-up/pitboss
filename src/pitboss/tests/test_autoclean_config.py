"""The ``[clean]`` keys of the automatic cleaning."""

import pathlib
import tomllib
import unittest

from .. import cleanconfig
from . import cleanworld
from .autocleanworld import has

same = cleanworld.same


def parse_clean(text: str) -> cleanconfig.Clean:
    """Read a ``[clean]`` table.

    Args:
        text: the TOML under the header.

    Returns:
        The settings.
    """
    return cleanconfig.from_document(tomllib.loads(f"[clean]\n{text}"))


def refusal(text: str) -> str:
    """The message of the error a table gives.

    Args:
        text: the TOML under the header.

    Returns:
        The message.
    """
    try:
        parse_clean(text)
    except ValueError as error:
        return str(error)
    return ""  # pragma: no cover


class TestConfig(unittest.TestCase):
    """The ``[clean]`` keys of the auto-clean."""

    def test_the_defaults(self) -> None:
        """The defaults are /tmp, a day, 90% and an hour."""
        found = parse_clean("")
        same(found.tmp_roots, (pathlib.Path("/tmp"),))
        same(found.tmp_patterns[0], "tmp????????")
        same(found.tmp_hours, 24.0)
        same(found.pressure_percent, 90.0)
        same(found.pressure_tmp_hours, 1.0)
        same(found.caches, ())

    def test_the_keys_are_read(self) -> None:
        """Every key can be set."""
        found = parse_clean(
            'tmp_roots = ["/var/tmp"]\ntmp_patterns = ["t*"]\ntmp_hours = 2\n'
            'pressure_percent = 80\npressure_tmp_hours = 0\ncaches = ["/c"]\n'
        )
        same(list(map(str, found.tmp_roots)), ["/var/tmp"])
        same(found.tmp_patterns, ("t*",))
        same(found.tmp_hours, 2.0)
        same(found.pressure_tmp_hours, 0.0)
        same(found.pressure_percent, 80.0)
        same(found.caches, (pathlib.Path("/c"),))

    def test_a_relative_root_is_refused(self) -> None:
        """The message says the paths must be absolute."""
        has(refusal('tmp_roots = ["tmp"]'), "must be absolute")

    def test_the_root_of_the_file_system_is_refused(self) -> None:
        """A cache cannot be the root."""
        has(refusal('caches = ["/"]'), "root of the file system")

    def test_a_negative_age_is_refused(self) -> None:
        """The message says it must not be negative."""
        has(refusal("tmp_hours = -1"), "must not be negative")

    def test_a_pressure_outside_the_range_is_refused(self) -> None:
        """0 and 101 are both outside (0, 100]."""
        has(refusal("pressure_percent = 0"), "above 0 and at most 100")
        has(refusal("pressure_percent = 101"), "above 0 and at most 100")

    def test_patterns_that_are_not_names_are_refused(self) -> None:
        """A number, a list of numbers, a path and an empty name are named."""
        has(refusal("tmp_patterns = 3"), "list of names")
        has(refusal("tmp_patterns = [3]"), "list of names")
        has(refusal('tmp_patterns = ["a/b"]'), "without /")
        has(refusal('tmp_patterns = [""]'), "without /")
