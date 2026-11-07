"""The reporter of the tests session: virtue's own, and the timing (pitboss#324).

The ``tests`` session of noxfile.py gives virtue ``--reporter`` with the name of
``TimingReporter``, so every run, whatever its arguments, ends with the total
time of the tests and the slowest ones with their times (keyword: test-timing).
"""

import unittest

from virtue.reporters import ComponentizedReporter

from ..noxcheck import SLOWEST_COUNT, TIMING_PREFIX


def timing_lines(durations: list[tuple[float, str]]) -> list[str]:
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


class TimingReporter(ComponentizedReporter):  # type: ignore[misc]
    """Virtue's default reporter, and at the end the time of the tests.

    The lines are printed when the run stops, which virtue does after a failing
    test too (``-x`` included), so a run that fails shows them.
    """

    def startTestRun(self) -> None:  # noqa: N802
        """Start the run with no durations."""
        self.durations: list[tuple[float, str]] = []
        super().startTestRun()

    def addDuration(  # noqa: N802
        self, test: unittest.TestCase, elapsed: float
    ) -> None:
        """Keep how long a test took.

        Args:
            test: the test.
            elapsed: its seconds.
        """
        self.durations.append((elapsed, test.id()))
        super().addDuration(test, elapsed)

    def stopTestRun(self) -> None:  # noqa: N802
        """Stop the run, then print the time."""
        super().stopTestRun()
        self.stream.writelines(f"{line}\n" for line in timing_lines(self.durations))
