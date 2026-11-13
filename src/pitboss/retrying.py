"""A read of GitHub that fails is tried again, then the command fails (read-retry).

The owner (the one-path plan, 3.2): "Retry with reasonable back-off with jitter and
otherwise fail pitboss next. If GitHub is having an outage, that's an LLM issue to
manage, not deterministic code." A transport error, a 5xx, a 429 and a 403 that
names a rate limit are tried again, at most ``ATTEMPTS`` times in all; before try k
(1, 2, 3) the wait is drawn uniformly from 0 to ``BASE`` times 2 to the k seconds. A
404, 410 or 422 is GitHub's answer (a blocker that is gone), as any other status
is; neither is tried again, and the caller reads it as it always did. After the
last try the read raises ``ReadFailed``, which only the command entry catches
(``cli_parser``): the command exits nonzero with the request and its status on
standard error, and no decision is made on a partial world.
"""

import dataclasses
import functools
import re
import subprocess
from typing import Callable, Sequence

from . import running
from .running import KeywordRun, Output

ATTEMPTS = 4
BASE = 0.5  # seconds: one measured request through gh (0.43 s)
ANSWERS = frozenset({404, 410, 422})
_STATUS = re.compile(r"HTTP (\d{3})")
_RATE = re.compile(r"rate limit", re.IGNORECASE)

Draw = Callable[[float], float]
Sleep = Callable[[float], None]


class ReadFailed(Exception):
    """A read of GitHub failed on every try: its text is the request and status."""


def status_of(error: subprocess.CalledProcessError) -> int | None:
    """The HTTP status ``gh`` printed for a failed read.

    Args:
        error: the failed run.

    Returns:
        The status, or None for a failure with none (a transport error).
    """
    found = _STATUS.search(str(error.stderr or ""))
    return int(found.group(1)) if found else None


def again(error: subprocess.CalledProcessError) -> bool:
    """Whether a failed read is tried again.

    Args:
        error: the failed run.

    Returns:
        True for a transport error, a 5xx, a 429 or a 403 for a rate limit.
    """
    status = status_of(error)
    if status is None:
        return True
    limited = status == 403 and bool(_RATE.search(str(error.stderr or "")))
    return status >= 500 or status == 429 or limited


def said(error: subprocess.CalledProcessError) -> str:
    """How a failed read failed, for the line on standard error.

    Args:
        error: the failed run.

    Returns:
        ``HTTP 503`` when ``gh`` printed a status, else ``gh exited N``.
    """
    status = status_of(error)
    return f"HTTP {status}" if status is not None else f"gh exited {error.returncode}"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Retried:
    """A runner whose ``gh api`` reads are tried again on a failure that may pass.

    Attributes:
        run: the runner the tries go through.
        draw: draws a wait uniformly from 0 to its argument (``random.uniform``).
        sleep: waits that many seconds (``time.sleep``).
    """

    run: KeywordRun
    draw: Draw
    sleep: Sleep

    def __call__(
        self, cmdargs: Sequence[str], /, *args: object, **kwargs: object
    ) -> Output:
        """Run a command; a ``gh api`` read that may pass is tried again.

        Args:
            cmdargs: the command line.
            *args: its other positional arguments.
            **kwargs: its keywords.

        Returns:
            The finished process; a read that failed on every try raises
            ``ReadFailed``.
        """
        return running.through(
            self.run, functools.partial(_tries, self), cmdargs, *args, **kwargs
        )


def _tries(retried: Retried, words: Sequence[str]) -> Output:
    last = ""
    for attempt in range(ATTEMPTS):
        if attempt:
            retried.sleep(retried.draw(BASE * 2**attempt))
        try:
            return retried.run(list(words))
        except subprocess.CalledProcessError as error:
            if not again(error):
                raise
            last = said(error)
    raise ReadFailed(f"{words[-1]}: {last}")


def with_retries(run: KeywordRun, draw: Draw, sleep: Sleep) -> KeywordRun:
    """A runner whose reads are tried again with a bounded wait, then fail.

    Args:
        run: the runner the tries go through.
        draw: draws a wait uniformly from 0 to its argument.
        sleep: waits that many seconds.

    Returns:
        The runner.
    """
    return Retried(run=run, draw=draw, sleep=sleep)
