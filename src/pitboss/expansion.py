"""Expand a template of shell commands into a body (keyword: expand, pitboss#117).

A template is text in which a line that starts with ``$ `` is a command. The
expansion prints each command exactly as written and the raw output, in a
fenced block whose opening line carries a digest of its contents, so a block a
person typed or edited is told from one ``pitboss expand`` produced.
"""

import dataclasses
import hashlib
import re
from typing import Callable, Sequence

MARK = "pitboss-expand"
DIGEST_KEY = "sha256="
DIGEST_LENGTH = 16
PROMPT = "$ "
ESCAPED_PROMPT = "\\$ "
NO_NEWLINE = "\\ No newline at end of output\n"
MIN_FENCE = 3
TICKS = re.compile(r"`+")


class TemplateError(ValueError):  # noqa: SLD504,SLD401
    """A template that cannot be expanded."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """What a command did.

    Attributes:
        status: its exit status.
        output: everything it printed, standard output and standard error
            together, as it printed it.
    """

    status: int
    output: str


Shell = Callable[[str], Outcome]


def digest(contents: str) -> str:
    """The digest a block's opening line carries.

    Args:
        contents: the lines between the fences.

    Returns:
        The first characters of the contents' SHA-256, in hex.
    """
    return hashlib.sha256(contents.encode("utf-8")).hexdigest()[:DIGEST_LENGTH]


def info(contents: str) -> str:
    """The text after the fence of a block ``expand`` produced.

    Args:
        contents: the lines between the fences.

    Returns:
        The mark and the digest.
    """
    return f"{MARK} {DIGEST_KEY}{digest(contents)}"


def contents(command: str, outcome: Outcome) -> str:
    """The lines of a block: the command, its output, its status when nonzero.

    The output is never trimmed or filtered. One that does not end with a
    newline gets a line saying so, so the closing fence is a line of its own.

    Args:
        command: the command line as written.
        outcome: what it did.

    Returns:
        The lines between the fences.
    """
    ended = outcome.output.endswith("\n") or not outcome.output
    return "".join(
        [
            f"{PROMPT}{command}\n",
            outcome.output,
            "" if ended else "\n" + NO_NEWLINE,
            f"exit status: {outcome.status}\n" if outcome.status else "",
        ]
    )


def block(command: str, outcome: Outcome) -> str:
    """The fenced block of a command.

    Args:
        command: the command line as written.
        outcome: what it did.

    Returns:
        The block, its fence longer than any run of backticks inside it.
    """
    inside = contents(command, outcome)
    longest = max((len(each) for each in TICKS.findall(inside)), default=0)
    fence = "`" * max(MIN_FENCE, longest + 1)
    return f"{fence}{info(inside)}\n{inside}{fence}\n"


def _command_of(line: str, number: int) -> str:
    command = line[len(PROMPT) :].rstrip("\r\n")
    if not command.strip():
        raise TemplateError(f"line {number}: a directive line has no command")
    return command


def _expand_line(shell: Shell, number: int, line: str) -> str:
    if line.startswith(ESCAPED_PROMPT):
        return PROMPT + line[len(ESCAPED_PROMPT) :]
    if not line.startswith(PROMPT):
        return line
    command = _command_of(line, number)
    return block(command, shell(command))


def commands(template: str) -> Sequence[str]:
    """The commands of a template, in order.

    Args:
        template: the template's text.

    Returns:
        Each directive's command line.
    """
    return [
        _command_of(line, number)
        for number, line in enumerate(template.splitlines(keepends=True), 1)
        if line.startswith(PROMPT)
    ]


def expand(template: str, shell: Shell) -> str:
    """Fill in a template.

    Every line of the template that is not a directive is kept as it is; a
    line that starts with ``\\$ `` is kept with the backslash removed. The
    commands are checked first, so a template with a bad directive runs
    nothing.

    Args:
        template: the template's text.
        shell: runs one command line.

    Returns:
        The body.
    """
    commands(template)
    return "".join(
        _expand_line(shell, number, line)
        for number, line in enumerate(template.splitlines(keepends=True), 1)
    )
