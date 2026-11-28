"""A write to GitHub is done when GitHub shows it (keyword: landed, pitboss#531).

Pitboss took a write for done from the command's exit and its answer: an
``act review`` whose POST came back 504 was reported or lost with no look at the
PR (quire#1138, repository-prototype#710), and 28 of the 34 write sites of
pitboss at c90493f read nothing back. Every write goes through ``write``, the one
caller of ``mutate`` in the package (P14.1, ``landedproofs``): it reads what the
write claims from GitHub (``landedseen``, one reading for each shape of ``gh``
words), and a write that has no reading is refused.

A write that raised is looked for before it is made again, so a POST GitHub kept
and answered 5xx is not made twice; one that returned but is not shown after the
waits is not made again either (a lagging read must not make it twice) and is
``NotLanded``.
"""

import dataclasses
import subprocess
import time
from typing import Callable, NoReturn, Sequence

from . import landedseen, retrying
from .landedwords import Words, parse
from .running import GitHub, NotLanded as NotLanded, Run

Pause = Callable[[float], None]
WAITS = (0.0, 0.5, 1.5, 3.0)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Tried:
    """One go at a write.

    Attributes:
        answer: what it printed.
        error: why it raised, None when it returned.
    """

    answer: str
    error: subprocess.CalledProcessError | None


def _make(github: GitHub, words: Sequence[str]) -> str:
    return github.mutate(list(words)).stdout


def _try(github: GitHub, words: Sequence[str]) -> Tried:
    answer, failure = "", None
    try:
        answer = _make(github, words)
    except subprocess.CalledProcessError as caught:
        failure = caught
    return Tried(answer=answer, error=failure)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """What a change that landed printed.

    Attributes:
        stdout: its output ("" when the change landed but its answer was an error).
        attempts: how many times the change was made (1 or 2).
    """

    stdout: str
    attempts: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Look:
    """What a write is looked for by.

    Attributes:
        github: the API.
        pause: waits a number of seconds.
        watch: the reading of the write's shape.
        parsed: the write.
        before: what the reading held before the write.
    """

    github: GitHub
    pause: Pause
    watch: landedseen.Watch
    parsed: Words
    before: object


def _shown(look: Look) -> bool:
    # a read that fails, or that GitHub has not caught up to, is "not yet"
    for delay in WAITS:
        look.pause(delay)
        try:
            if look.watch.seen(look.github, look.parsed, look.before):
                return True
        except (subprocess.CalledProcessError, retrying.ReadFailed):
            continue
    return False


def _printed(tried: Tried, look: Look) -> str:
    # what the write printed; a write that raised and landed printed nothing, so
    # what the reading found (the id or number of what it made) stands for it
    if tried.error is None:
        return tried.answer
    return look.watch.told(look.github, look.parsed, look.before)


def _unseen(tried: Tried, parsed: Words) -> NoReturn:
    # the command's own error when it raised, else a write that returned unseen
    if tried.error is not None:
        raise tried.error
    raise NotLanded(f"GitHub does not show {describe(parsed)}")


def _look(github: GitHub, words: Sequence[str], pause: Pause) -> Look:
    parsed = parse(words)
    watch = landedseen.watch_of(parsed) if parsed else None
    if parsed is None or watch is None:
        raise NotLanded(f"no read-back for the write {' '.join(words)}")
    before = watch.before(github, parsed)
    return Look(github=github, pause=pause, watch=watch, parsed=parsed, before=before)


def write(github: GitHub, words: Sequence[str], pause: Pause = time.sleep) -> Outcome:
    """Make one change to GitHub and read it back.

    A write that returned and is not shown, or whose words have no reading, is
    ``NotLanded``.

    Args:
        github: the API, whose ``mutate`` really makes the change.
        words: the ``gh`` command line.
        pause: waits a number of seconds (a test gives none).

    Returns:
        What the write printed and how many times it was made.
    """
    look = _look(github, words, pause)
    tried = Tried(answer="", error=None)
    for attempt in (1, 2):
        tried = _try(github, words)
        if _shown(look):
            return Outcome(stdout=_printed(tried, look), attempts=attempt)
        if tried.error is None:
            break
    return _unseen(tried, look.parsed)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Readback:
    """A runner whose every command is read back from GitHub.

    Attributes:
        github: the API, with the runner that makes the change.
        pause: waits a number of seconds.
        really: whether the runner writes (a dry run has nothing to read back).
    """

    github: GitHub
    pause: Pause
    really: bool

    def __call__(self, cmdargs: Sequence[str], /) -> Outcome:
        """Make one change and read it back.

        Args:
            cmdargs: the ``gh`` command line.

        Returns:
            What it printed.
        """
        if not self.really:
            return Outcome(stdout=self.github.mutate(list(cmdargs)).stdout, attempts=1)
        return write(self.github, cmdargs, self.pause)


def checked(run: Run, mutate: Run, really: bool, pause: Pause = time.sleep) -> Run:
    """The runner every change of an API goes through (P14.1).

    Args:
        run: the runner reads go through.
        mutate: the runner that makes the change (a dry run unless asked).
        really: whether ``mutate`` really writes; a dry run writes nothing, so it
            has nothing to read back.
        pause: waits a number of seconds (a test gives none).

    Returns:
        A runner that reads each change back from GitHub.
    """
    return Readback(github=GitHub(run=run, mutate=mutate), pause=pause, really=really)


def describe(parsed: Words) -> str:
    """What a write was, for a message.

    Args:
        parsed: the write.

    Returns:
        ``VERB path`` and its fields' names.
    """
    return f"{parsed.verb} {parsed.path} ({', '.join(sorted(parsed.fields))})"
