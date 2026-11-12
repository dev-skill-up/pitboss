"""The checks a repository declares for ``pitboss push`` (keyword: pre-push-check).

bats-lang/bats#654: ``tests/check-pins/check.sh`` was run with no arguments and the
push went through. A repository declares each check with the values of its
arguments, in ``[[pre_push]]``::

    [[pre_push]]
    name = "check-pins"
    command = ["tests/check-pins/check.sh", "{bats}", "{repository}"]
    ok = "check-pins: all passed"
    [pre_push.arguments]
    bats = "dist/debug/bats"
    repository = "../repository-prototype"

A word the command names that ``arguments`` does not give, or gives empty, refuses
the push naming it, and the check runs through ``gaterun``, so only an explicit ok
lets the push go.
"""

import pathlib
import re
from typing import Sequence

from . import config, gaterun

WORD = re.compile(r"\{(\w+)\}")


def missing(check: config.PrePush) -> Sequence[str]:
    """The words of a check's command that have no value.

    Args:
        check: the check.

    Returns:
        The words it names that ``arguments`` does not give or gives empty.
    """
    named = [word for part in check.command for word in WORD.findall(part)]
    return sorted({word for word in named if not check.arguments.get(word, "")})


def argv(check: config.PrePush) -> Sequence[str]:
    """The command line with the arguments put in.

    Args:
        check: the check, none of whose words is missing.

    Returns:
        The command line.
    """
    return [
        WORD.sub(lambda found: check.arguments[found.group(1)], part)
        for part in check.command
    ]


def refusals(
    safe_run: gaterun.Runner,
    checks: Sequence[config.PrePush],
    directory: pathlib.Path,
) -> Sequence[str]:
    """Run the checks of a push and say what refuses it.

    Args:
        safe_run: the runner of commands.
        checks: the checks the repository declares.
        directory: where they run, the checkout pushed from.

    Returns:
        The lines of every refusal; none when each check printed its ok. A check
        that lacks an argument is not run.
    """
    lines: list[str] = []
    for check in checks:
        lacking = missing(check)
        if lacking:
            lines.append(
                f"pre-push check {check.name}: no value for {', '.join(lacking)}"
                " (declare it under [pre_push.arguments])"
            )
            continue
        judged = gaterun.run(
            safe_run,
            argv(check),
            timeout=check.timeout,
            ok_text=check.ok,
            directory=str(directory),
        )
        if not judged.passed:
            lines.append(f"pre-push check {check.name} refused the push:")
            lines.extend(judged.output.rstrip("\n").splitlines()[-20:])
    return lines


def hook_failure(
    safe_run: gaterun.Runner,
    checks: Sequence[config.PrePush],
    directory: pathlib.Path,
) -> Sequence[str]:
    """Run the checks in order and stop at the first that fails.

    The keyword is pre-push-hook.

    Args:
        safe_run: the runner of commands.
        checks: the checks the repository declares.
        directory: where they run.

    Returns:
        The lines ``pre-push: check <n> (<name>) failed: <what>`` and
        ``fix: <the fix>`` of the first check that does not pass; none when each
        passes. A check lacking an argument fails, naming it.
    """
    for number, check in enumerate(checks, start=1):
        lines = refusals(safe_run, [check], directory)
        if lines:
            what = lines[0] if len(lines) == 1 else " ".join(lines[1:3])
            fix = check.fix or "run the check by hand and fix what it prints"
            return [
                f"pre-push: check {number} ({check.name}) failed: {what}",
                f"fix: {fix}",
            ]
    return []


def pushes_something(refs: str) -> bool:
    """Whether the ref lines git gave the hook push anything but deletions.

    Args:
        refs: the lines ``<local ref> <local sha> <remote ref> <remote sha>``.

    Returns:
        False when every line is a deletion (its local sha is all zeros) and
        there is at least one line; True when a ref is pushed or git gave none.
    """
    shas = [each.split()[1] for each in refs.splitlines() if len(each.split()) >= 2]
    return not shas or any(each.strip("0") for each in shas)
