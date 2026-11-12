"""The one runner of a gate: anything but an explicit ok is a refusal (keyword: gate-run).

bats-lang/bats#654: a pre-push check ran ``tests/check-pins/check.sh`` with no
arguments (``$1: unbound variable``, ``FAIL: pinned was refused``) and the push went
through. A gate that is a command passes only when it exited 0, printed something
(or the text its ``ok`` names) and said nothing of a crash; a non-zero status, a
signal, a command that cannot start, a timeout, a missing argument and an empty
output are each a refusal of their own.
"""

import dataclasses
import enum
import subprocess
from typing import Mapping, Protocol, Sequence

from . import expansion

CRASHED = ("Traceback (most recent call last)", "command not found", "core dumped")
MISSING = ("unbound variable", "missing argument", "missing required argument")
TIMEOUT_STATUS = 124
CANNOT_START_STATUS = 127
EMPTY_STATUS = 1


class Finished(Protocol):
    """What a finished gate gives back."""

    @property
    def returncode(self) -> int:
        """The exit status.

        Returns:
            The status.
        """

    @property
    def stdout(self) -> str | None:
        """What it printed.

        Returns:
            The output.
        """


class Runner(Protocol):
    """Runs a command line with the keywords of ``safe_run``."""

    def __call__(
        self, cmdargs: Sequence[str], /, *args: object, **kwargs: object
    ) -> Finished:
        """Run a command.

        Args:
            cmdargs: the command line.
            *args: its other positional arguments.
            **kwargs: its keywords.

        Returns:
            The finished process.
        """


class Mode(enum.Enum):
    """How a gate came out.

    Attributes:
        OK: exit 0, an output, no sign of a crash, and the declared ok text.
        NONZERO: a non-zero exit status.
        CRASH: a signal, a command that cannot start, or a crash in its output.
        EMPTY: exit 0 but no output, or none with the declared ok text.
        TIMEOUT: it did not finish in time.
        MISSING_ARGUMENT: an argument it needs was not given.
    """

    OK = "ok"
    NONZERO = "exited non-zero"
    CRASH = "crashed"
    EMPTY = "printed no explicit ok"
    TIMEOUT = "timed out"
    MISSING_ARGUMENT = "lacks an argument"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Judged:
    """What a gate came to.

    Attributes:
        mode: which case.
        status: the exit status, 0 only for ``Mode.OK``.
        output: what it printed, with the reason a refusal adds at the end.
    """

    mode: Mode
    status: int
    output: str

    @property
    def passed(self) -> bool:
        """Whether the gate is ok.

        Returns:
            True only for ``Mode.OK``.
        """
        return self.mode is Mode.OK


def judge(status: int, output: str, *, failed: str = "", ok_text: str = "") -> Judged:
    """Judge a finished gate.

    Args:
        status: its exit status, ignored when ``failed`` is given.
        output: what it printed.
        failed: ``timeout`` or ``start`` when it did not finish or start.
        ok_text: the text its output must hold to be ok, empty for any output.

    Returns:
        The verdict; ok only when nothing refuses it.
    """
    if failed == "timeout":
        return _refused(Mode.TIMEOUT, TIMEOUT_STATUS, output)
    if failed == "start":
        return _refused(Mode.CRASH, CANNOT_START_STATUS, output)
    code = status
    if any(each in output for each in MISSING):
        return _refused(Mode.MISSING_ARGUMENT, code or EMPTY_STATUS, output)
    if code < 0 or any(each in output for each in CRASHED):
        return _refused(Mode.CRASH, code or EMPTY_STATUS, output)
    if code:
        return _refused(Mode.NONZERO, code, output)
    named = ok_text in output if ok_text else bool(output.strip())
    if not named:
        return _refused(Mode.EMPTY, EMPTY_STATUS, output)
    return Judged(mode=Mode.OK, status=0, output=output)


def _refused(mode: Mode, status: int, output: str) -> Judged:
    return Judged(
        mode=mode, status=status, output=f"{output}gate refused: {mode.value}\n"
    )


def run(
    safe_run: Runner,
    command: Sequence[str],
    *,
    timeout: int,
    ok_text: str = "",
    environment: Mapping[str, str] | None = None,
    directory: str | None = None,
) -> Judged:
    """Run a command as a gate.

    Args:
        safe_run: the runner of commands.
        command: the command line.
        timeout: the most seconds it may run.
        ok_text: the text its output must hold, empty for any output.
        environment: the child's environment, this process's when none.
        directory: its working directory, this process's when none.

    Returns:
        The verdict (never raises for a failure of the command).
    """
    given: dict[str, object] = {}
    if environment is not None:
        given["env"] = environment
    if directory is not None:
        given["cwd"] = directory
    try:
        done = safe_run(
            list(command),
            check=False,
            timeout=timeout,
            capture_output=False,  # one stream, not the runner default (gate-run)
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **given,
        )
    except subprocess.TimeoutExpired:
        return judge(0, "", failed="timeout")
    except subprocess.CalledProcessError as failure:  # a runner that checks
        said = f"{failure.stdout or ''}{failure.stderr or ''}"
        return judge(failure.returncode, said)
    except OSError as error:
        return judge(0, f"cannot start: {error}\n", failed="start")
    return judge(int(done.returncode), str(done.stdout or ""), ok_text=ok_text)


def outcome(judged: Judged) -> expansion.Outcome:
    """The verdict as the outcome the sessions of ``nox`` read.

    Args:
        judged: the verdict.

    Returns:
        Status 0 only for an ok gate, and the output.
    """
    return expansion.Outcome(status=judged.status, output=judged.output)
