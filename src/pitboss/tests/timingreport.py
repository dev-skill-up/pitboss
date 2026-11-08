"""The reporter of the tests session: virtue's own, and the timing (pitboss#324).

The ``tests`` session of noxfile.py gives virtue ``--reporter`` with the name of
``TimingReporter``, so every run, whatever its arguments, ends with the total
time of the tests and the slowest ones with their times (keyword: test-timing).
"""

import unittest
from typing import Sequence

from virtue.reporters import ComponentizedReporter as Virtue

from ..noxcheck import LEAK_PREFIX, OUTSIDE_TESTS, SLOWEST_COUNT, TIMING_PREFIX
from . import scratch


def timing_lines(
    durations: Sequence[tuple[float, str]],
) -> Sequence[str]:
    """The lines that say how long the tests took.

    Args:
        durations: the seconds and the id of each test that ran.

    Returns:
        The total line, then one line for each of the slowest tests, slowest
        first; each starts with ``noxcheck.TIMING_PREFIX``.
    """
    total = sum(seconds for seconds, _ in durations)
    lines = [f"{TIMING_PREFIX}total {total:.3f}s in {len(durations)} tests"]
    slowest = sorted(durations, key=lambda each: (-each[0], each[1]))[:SLOWEST_COUNT]
    for place, (seconds, name) in enumerate(slowest, start=1):
        lines.append(f"{TIMING_PREFIX}slowest {place} {seconds:.3f}s {name}")
    return lines


def leak_lines(leaks: Sequence[tuple[str, str]]) -> Sequence[str]:
    """The lines that name what tests left in the ``TMPDIR`` of the run.

    Args:
        leaks: the id of the test (``noxcheck.OUTSIDE_TESTS`` for a name that
            no test explains) and the name it left, in the order found.

    Returns:
        A line for each, starting with ``noxcheck.LEAK_PREFIX``.
    """
    return [f"{LEAK_PREFIX}{each} {name}" for each, name in leaks]


class TimingReporter(Virtue):  # type: ignore[misc]  # noqa: SLD504,SLD401
    """Virtue's default reporter, the leak check, and the time of the tests.

    The timing lines are printed when the run stops, which virtue does after a
    failing test too (``-x`` included), so a run that fails shows them. A run
    that passes and left a name in its ``TMPDIR`` fails after the suite, with a
    line for each name and the test that left it (keyword: test-leak,
    pitboss#346); a run that fails is not checked, its directory is kept for
    debugging.
    """

    def startTestRun(self) -> None:  # noqa: N802,SLD303
        """Start the run with no durations and no leaks."""
        self.durations: list[tuple[float, str]] = []
        self.leaks: list[tuple[str, str]] = []
        self.at_start = scratch.listing()
        super().startTestRun()

    def startTest(self, test: unittest.TestCase) -> None:  # noqa: N802,SLD303
        """Note the names in the ``TMPDIR`` before the test.

        Args:
            test: the test.
        """
        scratch.begin(test)
        self.before = scratch.listing()
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase) -> None:  # noqa: N802,SLD303
        """Keep the names the test left, after its cleanups have run.

        Args:
            test: the test.
        """
        found = scratch.fresh(self.before, scratch.listing())
        self.leaks.extend((test.id(), name) for name in found)
        scratch.end()
        super().stopTest(test)

    def wasSuccessful(self) -> bool:  # noqa: N802,SLD303
        """Whether the run passed and left nothing in its ``TMPDIR``.

        Returns:
            True when virtue's own answer is yes and no name was left.
        """
        return bool(super().wasSuccessful()) and not self.leaks

    def addDuration(  # noqa: N802,SLD303
        self, test: unittest.TestCase, elapsed: float
    ) -> None:
        """Keep how long a test took.

        Args:
            test: the test.
            elapsed: its seconds.
        """
        self.durations.append((elapsed, test.id()))
        super().addDuration(test, elapsed)

    def stopTestRun(self) -> None:  # noqa: N802,SLD303
        """Stop the run, then print the names left (a run that passed), the time."""
        super().stopTestRun()
        if super().wasSuccessful():
            named = {name for _, name in self.leaks}
            stray = scratch.fresh(self.at_start, scratch.listing())
            self.leaks.extend(
                (OUTSIDE_TESTS, name) for name in stray if name not in named
            )
            self.stream.writelines(f"{line}\n" for line in leak_lines(self.leaks))
        self.stream.writelines(f"{line}\n" for line in timing_lines(self.durations))
