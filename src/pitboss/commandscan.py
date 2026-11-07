"""The commands, scanned once per process (keyword: scan-once).

The commands of the package are the same for the life of the process, and
``venusian.scan`` (which ``gather`` calls) took 39 ms of every call of the parser
(pitboss#327), so a scan is made the first time it is asked and its result is kept.
"""

import functools
from collections.abc import Callable, Iterable, Mapping

Collect = Callable[[], Mapping[str, Iterable[object]]]


@functools.cache
def scanned(collect: Collect) -> Mapping[str, Iterable[object]]:
    """The commands a scan registered, scanned on the first call only.

    Args:
        collect: the scan, ``ENTRY_DATA.collector.collect`` (a test gives one
            that counts its calls); the same scan, however it is spelled, is
            made once.

    Returns:
        What ``collect`` gave the first time; callers only read it.
    """
    return collect()
