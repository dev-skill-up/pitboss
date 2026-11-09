"""Run ``pitboss plan-check`` on a body in a real repository (pitboss#398)."""

from . import diffrepo, world
from .linting import write_text
from .test_expand_commands import real_world


def body_of(rows: str, evidence: str = "") -> str:
    """A body with a Plan, an Execution and maybe an Evidence section.

    Args:
        rows: the Plan's rows.
        evidence: the text under an Evidence heading; none for no heading.

    Returns:
        The body.
    """
    section = f"## Evidence\n\n{evidence}" if evidence else ""
    return f"## Plan\n{rows}\n## Execution\nx\n\n{section}"


def plan_check(repo: diffrepo.Repository, body: str) -> world.Result:
    """Run ``pitboss plan-check`` on a body, the repository's ``work`` the head.

    Args:
        repo: the repository.
        body: the PR's body.

    Returns:
        What it did.
    """
    return world.invoke(
        real_world(),
        "plan-check",
        write_text("body.txt", body),
        "--repo",
        str(repo.root),
        "--head",
        "HEAD",
    )


def refused_with(done: world.Result, *words: str) -> bool:
    """Whether a check refused (exit 1) and printed every word.

    Args:
        done: what it did.
        *words: the texts the output must hold.

    Returns:
        True when it did.
    """
    return done.code == 1 and all(each in done.out for each in words)


def passed(done: world.Result) -> bool:
    """Whether a check ended ``Plan check: ok``.

    Args:
        done: what it did.

    Returns:
        True when it exited 0 and said so.
    """
    return done.code == 0 and "Plan check: ok" in done.out
