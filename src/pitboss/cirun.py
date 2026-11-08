"""A CI pointer names the run of the body's head (keyword: ci-run, pitboss#317).

Seen on pitboss#372: the Plan's CI pointer named the push run of the commit before
a merge of main, so a review read a run that proved nothing about the head.
``pitboss plan-check`` reads each run a CI pointer row names by its address
(``https://github.com/OWNER/NAME/actions/runs/ID``, a job address of it too) and
refuses the Plan when the run's ``head_sha`` is not the body's last ``Head:`` line.
It is a read of the run and waits for nothing. The module reads nothing itself:
the head of a run is given by a reader.
"""

import re
from typing import Callable, Sequence

from . import cipointer

CHECK = "ci-run"
RUN = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/actions/runs/(\d+)")
FULL = re.compile(r"^[0-9a-f]{40}$")
HeadOf = Callable[[str, int], str | None]


def findings(section: str, head: str, head_of: HeadOf) -> Sequence[str]:
    """What the CI pointers of a Plan name that is not the run of the head.

    Args:
        section: the Plan section.
        head: the body's last ``Head:`` line (the full SHA); with anything else
            there is nothing to compare with and no run is read.
        head_of: reads the ``head_sha`` of a run, given its repository and id;
            None when the run cannot be read.

    Returns:
        A finding for each run a pointer row names whose head is another commit
        or that cannot be read, naming the run, its SHA and the ``Head:`` line.
    """
    if not FULL.match(head):
        return []
    found: list[str] = []
    for number, text in cipointer.rows(section):
        named = RUN.findall(text) if cipointer.read(text) else []
        for slug, run in dict.fromkeys(named):
            found.extend(_finding(number, slug, run, head, head_of))
    return found


def _finding(
    number: int, slug: str, run: str, head: str, head_of: HeadOf
) -> Sequence[str]:
    url = f"https://github.com/{slug}/actions/runs/{run}"
    sha = head_of(slug, int(run))
    if sha is None:
        return [
            f"{CHECK}: Plan line {number} names the run {url}, which cannot be read"
        ]
    if sha == head:
        return []
    return [
        f"{CHECK}: Plan line {number} names the run {url} of head {sha}, but the"
        f" body's last Head: line is {head}: name the run of the head"
    ]
