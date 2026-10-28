"""Small pieces of Markdown the report is made of."""

from typing import Mapping, Sequence

from . import config, redcost, redshapes, redtickets, shapes

COMMAND_WIDTH = 200


def link(text: str, url: str) -> str:
    """A Markdown link.

    Args:
        text: its text.
        url: its target.

    Returns:
        The link.
    """
    return f"[{text}]({url})"


def _site(repo: config.Repo, text: str, path: str) -> str:
    return link(text, f"https://github.com/{repo.slug}/{path}")


def _numbered(identifier: int, url: str) -> str:
    return link(str(identifier), url)


def commit_ref(repo: config.Repo, sha: str) -> str:
    """A commit as a link to its page.

    Args:
        repo: its repository.
        sha: its SHA.

    Returns:
        The link, with the first seven digits as its text.
    """
    return _site(repo, sha[:7], f"commit/{sha}")


def pull_ref(repo: config.Repo, number: int) -> str:
    """A PR as a link to its page.

    Args:
        repo: its repository.
        number: its number.

    Returns:
        The link.
    """
    return _site(repo, f"#{number}", f"pull/{number}")


def run_pulls(repo: config.Repo, run: shapes.WindowRun) -> str:
    """The PRs a run is tied to, as links.

    Args:
        repo: the repository.
        run: the run.

    Returns:
        The links, or ``none``.
    """
    return ", ".join(pull_ref(repo, number) for number in run.pulls) or "none"


def run_ref(run: shapes.WindowRun) -> str:
    """A run as a link to its page.

    Args:
        run: the run.

    Returns:
        The link.
    """
    return _numbered(run.id, run.url)


def run_list(ids: Sequence[int], urls: Mapping[int, str]) -> str:
    """Run ids as links.

    Args:
        ids: the run ids.
        urls: each id's page.

    Returns:
        The links, comma separated.
    """
    return ", ".join(link(str(each), urls[each]) for each in ids)


def ticket_list(tickets: Sequence[redtickets.Ticket]) -> str:
    """Tickets as links.

    Args:
        tickets: the tickets.

    Returns:
        The links, comma separated.
    """
    return ", ".join(
        link(redtickets.name(each), redtickets.url(each)) for each in tickets
    )


def job_ref(job: redshapes.Job) -> str:
    """A job as a link to its page.

    Args:
        job: the job.

    Returns:
        The link, naming the job and its id.
    """
    return f"{job.name} (job {_numbered(job.id, job.url)})"


def command_line(command: str) -> str:
    """Make a shell command one short line of inline code.

    Args:
        command: the command, which may span lines and hold backticks.

    Returns:
        Its words on one line, cut at ``COMMAND_WIDTH`` characters.
    """
    words = " ".join(command.split()).replace("`", "'")
    cut = words if len(words) <= COMMAND_WIDTH else words[:COMMAND_WIDTH] + "..."
    return f"`{cut}`"


def duration(total: int | None) -> str:
    """Say seconds as hours, minutes and seconds.

    Args:
        total: seconds, or ``None`` for a time that does not exist.

    Returns:
        The duration, or ``none``.
    """
    if total is None:
        return "none"
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return (
        f"{hours}h {minutes:02d}m {secs:02d}s" if hours else f"{minutes}m {secs:02d}s"
    )


def minutes(total: int) -> str:
    """Say seconds as job-minutes.

    Args:
        total: seconds.

    Returns:
        The minutes with one decimal.
    """
    return f"{total / 60:.1f}"


def percent(part: int, whole: int) -> str:
    """A percentage.

    Args:
        part: the part.
        whole: the whole.

    Returns:
        The percentage, or ``n/a`` for an empty whole.
    """
    return f"{100 * part / whole:.0f}%" if whole else "n/a"


def spread_text(found: redcost.Spread | None) -> str:
    """Say a distribution.

    Args:
        found: the distribution.

    Returns:
        Its count, low, median and high.
    """
    if found is None:
        return "none (no run has this)"
    return (
        f"n={found.count}, low {duration(found.low)}, median "
        f"{duration(found.median)}, high {duration(found.high)}"
    )
