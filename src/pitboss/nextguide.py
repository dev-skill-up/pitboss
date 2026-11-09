"""What ``pitboss next TICKET`` prints for the Plan a worker is about to write.

Two things the brief cannot state before the worker writes (keyword: next-guide,
pitboss#282): the marker the ticket's Done-when bullets are written with (the
worker of bats-lang/bats#621 wrote ``- `` for the ticket's ``* ``), and the job
names of the repository's check workflow, matrix expressions as written (it named
``fixtures (shard N)``, which is no job; the job is ``fixtures (shard ${{
matrix.shard }})``). The module reads nothing: the texts are given.
"""

from typing import Sequence

from . import ciworkflow, ticketwhen

DONE_WHEN = "DONE-WHEN"
CI_JOBS = "CI JOBS"
CHECK_WORKFLOW = ".github/workflows/check.yml"


def done_when_lines(ticket: str, body: str) -> Sequence[str]:
    """The lines that give the Done-when bullets as the ticket has them.

    Args:
        ticket: the ticket, ``owner/repo#N``.
        body: the ticket's text.

    Returns:
        A header line and a line for each bullet, marker included; none when the
        Done-when has no bullet.
    """
    found = ticketwhen.bullets(body)
    if not found:
        return []
    header = (
        f"{DONE_WHEN}: {ticket}: copy each bullet word for word, with the marker the"
        " ticket gives it, into a numbered Plan row of its own:"
    )
    return [header, *found]


def ci_jobs_line(ticket: str, workflow: str | None) -> str:
    """The line that names the jobs a CI pointer may name.

    Args:
        ticket: the ticket, ``owner/repo#N``.
        workflow: the text of the repository's check workflow, None when it has
            none.

    Returns:
        The line, with each job's ``name:`` (its key when it has none) as written
        in the file; "" when there is no workflow or it has no job.
    """
    if workflow is None:
        return ""
    titles = ciworkflow.read(workflow).titles
    if not titles:
        return ""
    return (
        f"{CI_JOBS}: {ticket}: the jobs of `{CHECK_WORKFLOW}`, as written (a CI"
        f" pointer names one of them): {'; '.join(titles)}"
    )
