"""A read made once is made once, whichever threads ask at the same moment."""

import threading
import unittest

from hamcrest import assert_that, equal_to

from .. import concurrently


class TestOnce(unittest.TestCase):
    """The function runs once for each key."""

    def test_two_threads_asking_together_make_one_call(self) -> None:
        """The second asker waits for the first's answer."""
        started, calls = threading.Event(), []

        def slow(name: str) -> str:
            calls.append(name)
            started.wait(1)
            return name.upper()

        ask = concurrently.once(slow, str)
        answers = []
        threads = [
            threading.Thread(target=lambda: answers.append(ask("a"))) for _ in range(4)
        ]
        for each in threads:
            each.start()
        started.set()
        for each in threads:
            each.join()
        assert_that((calls, answers), equal_to((["a"], ["A"] * 4)))

    def test_each_key_has_its_own_call(self) -> None:
        """Two keys are two calls, and each is answered again from its own."""
        calls: list[str] = []

        def echo(name: str) -> str:
            calls.append(name)
            return name.lower()

        ask = concurrently.once(echo, lambda name: name[:1])
        assert_that([ask("a"), ask("b"), ask("a")], equal_to(["a", "b", "a"]))
        assert_that(calls, equal_to(["a", "b"]))
