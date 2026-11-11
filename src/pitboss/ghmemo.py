"""Each read of GitHub made once in a run (keyword: read-memo, pitboss#453).

``slots next`` asked for the same path more than once (a ticket's comments for
the PR that fixes it and again for its blockers) and could not start a read
before the one it followed was done. A runner that remembers the answer of a
``gh api`` read, and lets a second asker wait for the first, makes each read
once and lets a read be started early (``prefetch``). It is made for one run of
one command that changes nothing it reads again.
"""

import concurrent.futures
import dataclasses
import threading
from typing import MutableMapping, Sequence

from .running import KeywordRun, Output

LIMIT = 24  # reads running at once, over every pool that asks


def _claim(memo: "Memo", key: str) -> tuple["concurrent.futures.Future[Output]", bool]:
    # the answer a read will get, and whether the caller is to make it
    with memo.lock:
        known = memo.reads.get(key)
        if known is not None:
            return known, False
        made: "concurrent.futures.Future[Output]" = concurrent.futures.Future()
        memo.reads[key] = made
        return made, True


def _failed(known: "concurrent.futures.Future[Output]", why: BaseException) -> None:
    known.set_exception(why)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Memo:
    """The reads of a run.

    Attributes:
        run: the runner the reads go through the first time.
        lock: held while the reads are looked up.
        turns: the reads that run at once.
        reads: each read command (as one text) and the answer it gets.
    """

    run: KeywordRun
    lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)
    turns: threading.Semaphore = dataclasses.field(
        default_factory=lambda: threading.Semaphore(LIMIT)
    )
    reads: MutableMapping[str, "concurrent.futures.Future[Output]"] = dataclasses.field(
        default_factory=dict
    )

    def __call__(
        self, cmdargs: Sequence[str], /, *args: object, **kwargs: object
    ) -> Output:
        """Run a command; a ``gh api`` read already made is not made again.

        Args:
            cmdargs: the command line.
            *args: its other positional arguments.
            **kwargs: its keywords.

        Returns:
            The finished process, as the first asker got it; the same error is
            raised for a read that failed.
        """
        words = tuple(cmdargs)
        if words[:2] != ("gh", "api") or len(words) != 3 or args or kwargs:
            return self.run(cmdargs, *args, **kwargs)
        known, first = _claim(self, "\0".join(words))
        if first:
            try:
                with self.turns:
                    known.set_result(self.run(cmdargs))
            except BaseException as why:
                _failed(known, why)
        return known.result()


def memoized(run: KeywordRun) -> KeywordRun:
    """A runner that makes each ``gh api`` read once.

    Args:
        run: the runner reads go through.

    Returns:
        The runner that remembers.
    """
    return Memo(run=run)
