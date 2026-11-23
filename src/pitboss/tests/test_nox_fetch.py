"""The publish action's file is fetched again after a server error (fetch-retry).

dry_release of 5a40f7f failed on a 503 ``Backend.max_conn reached`` from
raw.githubusercontent.com; a server error is tried again with backoff, a 4xx is not.
"""

import io
import types
import unittest
import urllib.error
from collections.abc import Callable, Iterator, MutableSequence, Sequence
from email.message import Message

from hamcrest import assert_that, equal_to

from .test_noxfile import noxfile_module

BODY = "FROM python:3.13"


Opener = Callable[[str, int], io.BytesIO]


def answering(statuses: Iterator[int], asked: MutableSequence[str]) -> Opener:
    """A ``urlopen`` that answers each request with the next status, then 200.

    Args:
        statuses: the statuses of the first requests.
        asked: where each url asked is kept.

    Returns:
        The function.
    """

    def urlopen(url: str, timeout: int) -> io.BytesIO:
        asked.append(url)
        status = next(statuses, 200)
        if status != 200:
            raise urllib.error.HTTPError(url, status, "no", Message(), None)
        return io.BytesIO(BODY.encode())

    return urlopen


def fetched(*statuses: int) -> tuple[str, int, Sequence[int]]:
    """Fetch the publish action's file from a server that answers as told.

    Args:
        *statuses: the statuses of the first requests.

    Returns:
        The text, the requests made and the seconds slept.
    """
    module = noxfile_module()
    asked: list[str] = []
    slept: list[int] = []
    request = types.SimpleNamespace(urlopen=answering(iter(statuses), asked))
    module.__dict__["urllib"] = types.SimpleNamespace(
        request=request, error=urllib.error
    )
    module.__dict__["time"] = types.SimpleNamespace(sleep=slept.append)
    text = module.publish_action_file("a" * 40, "Dockerfile")
    return text, len(asked), slept


class TestFetchRetry(unittest.TestCase):
    """The fetch after a server error."""

    def test_a_503_is_tried_again_with_backoff(self) -> None:
        """Two 503s then the file: three requests, the waits grow."""
        assert_that(fetched(503, 503), equal_to((BODY, 3, [1, 2])))

    def test_a_404_is_raised_at_once(self) -> None:
        """A retry cannot change a 4xx."""
        with self.assertRaises(urllib.error.HTTPError):
            fetched(404)

    def test_a_503_that_never_ends_is_raised_after_the_tries(self) -> None:
        """The last try's error is the answer."""
        with self.assertRaises(urllib.error.HTTPError):
            fetched(*[503] * 9)
