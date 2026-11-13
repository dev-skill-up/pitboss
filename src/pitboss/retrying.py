"""A read of GitHub that fails is tried again, then the command fails (read-retry).

The owner (the one-path plan, 3.2): "Retry with reasonable back-off with jitter and
otherwise fail pitboss next. If GitHub is having an outage, that's an LLM issue to
manage, not deterministic code." A transport error, a 5xx, a 429 and a 403 that
names a rate limit are tried again, at most ``ATTEMPTS`` times in all; before try k
(1, 2, 3) the wait is drawn uniformly from 0 to ``BASE`` times 2 to the k seconds. A
404, 410 or 422 is GitHub's answer (a blocker that is gone), as any other status
is; neither is tried again, and the caller reads it as it always did. A read is made
with ``--include``, so a ``Retry-After`` of the failed try is read: up to ``CAP``
seconds it is the lower end of the wait. After the last try the read raises
``ReadFailed``, which only the command entry catches (``cli_parser``): the command
exits nonzero with the request and its status on standard error, and no decision
is made on a partial world.
"""

import dataclasses
import re
import subprocess
from typing import Callable, Sequence

from .running import KeywordRun, Output

ATTEMPTS = 4
BASE = 0.5  # seconds: one measured request through gh (0.43 s)
ANSWERS = frozenset({404, 410, 422})
WRITES = frozenset({"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"})
_STATUS = re.compile(r"HTTP (\d{3})")
_RATE = re.compile(r"rate limit", re.IGNORECASE)
CAP = 4.0  # seconds: the most a Retry-After raises the lower end of a wait
_LINE = r"[^\r\n]*\r?\n"  # the rest of a line of a response's head
_HEAD = re.compile(rf"HTTP/[0-9.]+ [0-9]{{3}}{_LINE}(?:[A-Za-z0-9-]+:{_LINE})*\r?\n")
_AFTER = re.compile(r"(?im)^Retry-After: *([0-9]+)\s*$")

Draw = Callable[[float], float]
Sleep = Callable[[float], None]


class ReadFailed(Exception):
    """A read of GitHub failed on every try: its text is the request and status."""


def reads(words: Sequence[str]) -> bool:
    """Whether a command line is a read of GitHub (a write is never tried again).

    Args:
        words: the command line.

    Returns:
        True for ``gh api`` with no method and no field (``-f`` makes a POST), and
        for a GraphQL query that is no mutation.
    """
    if words[:2] != ["gh", "api"]:
        return False
    if "graphql" in words:
        return not any(each.startswith("query=mutation") for each in words)
    return not WRITES & set(words)


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
class Read:
    """A read's output with the response headers taken out.

    Attributes:
        stdout: the bodies, as ``gh`` printed them without ``--include``.
    """

    stdout: str


def body(text: str) -> str:
    """The output of a read made with ``--include``, without its header blocks.

    Args:
        text: what ``gh`` printed (one header block for each page).

    Returns:
        The bodies alone.
    """
    return _HEAD.sub("", text)


def retry_after(error: subprocess.CalledProcessError) -> float:
    """The lower end of the wait before the next try: the failed try's Retry-After.

    Args:
        error: the failed run of a read made with ``--include``.

    Returns:
        Its ``Retry-After`` in seconds, at most ``CAP``; 0 when it has none.
    """
    found = _AFTER.search(str(error.stdout or ""))
    return min(float(found.group(1)), CAP) if found else 0.0


def wait(draw: Draw, attempt: int, lower: float) -> float:
    """The wait before try ``attempt``: uniform from the lower end to its bound.

    Args:
        draw: draws uniformly from 0 to its argument.
        attempt: the try about to be made (1, 2, 3).
        lower: the failed try's Retry-After, at most ``CAP``.

    Returns:
        ``lower`` plus a draw up to ``BASE`` times 2 to the attempt less ``lower``.
    """
    return lower + draw(max(BASE * 2**attempt - lower, 0.0))


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
        words = list(cmdargs)
        if args or kwargs or not reads(words):
            return self.run(cmdargs, *args, **kwargs)
        return _tries(self, words)


def _tries(retried: Retried, words: Sequence[str]) -> Output:
    included = [*words[:2], "--include", *words[2:]]
    last, lower = "", 0.0
    for attempt in range(ATTEMPTS):
        if attempt:
            retried.sleep(wait(retried.draw, attempt, lower))
        try:
            return Read(stdout=body(retried.run(included).stdout))
        except subprocess.CalledProcessError as error:
            if not again(error):
                error.stdout = body(str(error.stdout or ""))
                raise
            last, lower = said(error), retry_after(error)
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
