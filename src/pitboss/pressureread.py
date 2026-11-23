"""Whether the runners are held now, for the verbs that cost runs (act-pressure)."""

from . import queue, queuereads, report, reading


def look(found: reading.Reading) -> queue.Seen:
    """What the runners show now; nothing is written.

    Args:
        found: the context.

    Returns:
        The look.
    """
    runs = queuereads.runner_runs(found, queuereads.read_queue_runs(found))
    return queue.look(found.github, runs, found.settings.runners, found.now)


def held_line(found: reading.Reading) -> str:
    """The runner-pressure line when jobs wait or quiet minutes are owed, else empty.

    Nothing is written: the look is not counted in the quiet period (``push`` does).

    Args:
        found: the context.

    Returns:
        The line, empty when nothing is held or the project has no ``[runners]``.
    """
    runners = found.settings.runners
    if not runners.held:
        return ""
    looked = look(found)
    return report.seen_line(looked) if looked.waiting or looked.owed else ""
