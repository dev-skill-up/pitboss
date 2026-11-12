"""Expand a template of shell commands into a body (keyword: expand, pitboss#117).

A template is text in which a line that starts with ``$ `` is a command. The
expansion prints each command exactly as written and the raw output, in a
fenced block whose opening line carries a digest of its contents, so a block a
person typed or edited is told from one ``pitboss expand`` produced.
"""

import dataclasses
import functools
import hashlib
import re
from typing import Callable, Sequence

MARK = "pitboss-expand"
DIGEST_KEY = "sha256="
DIGEST_LENGTH = 16
HEAD_KEY = "head="
HEAD_LENGTH = 40
PROMPT = "$ "
ESCAPED_PROMPT = "\\$ "
NO_NEWLINE = "\\ No newline at end of output\n"
MIN_FENCE = 3
TICKS = re.compile(r"`+")
RUN_ADDRESS = re.compile(
    r"(https://github\.com/[\w.-]+/[\w.-]+)/actions/runs/\d+(?:/job/\d+)?"
)


BOM = "﻿"
# the store wraps a URL it finds in a line in a pair of backticks (pitboss#164)
WRAPPED_URL = re.compile(r"``(https?://[^`\s]+)``")


def normalise(output: str) -> str:
    """Remove what a store drops from a command's output (keyword: store-form).

    Args:
        output: what a command printed.

    Returns:
        The output without a byte order mark and without carriage returns.
    """
    return output.replace(BOM, "").replace("\r", "")


def stored_form(text: str) -> str:
    """The form of a block's lines that a store that rewrites them keeps.

    Args:
        text: the lines between the fences, as stored.

    Returns:
        The text without a byte order mark or carriage return, and with a URL
        the store wrapped in double backticks unwrapped.
    """
    return WRAPPED_URL.sub(r"\1", normalise(text))


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

    It is taken over ``stored_form`` of the lines, so a block and the block a
    store rewrote (keyword: store-form, pitboss#164) carry the same digest.

    Args:
        contents: the lines between the fences.

    Returns:
        The first characters of the contents' SHA-256, in hex.
    """
    return hashlib.sha256(stored_form(contents).encode()).hexdigest()[:DIGEST_LENGTH]


def info(contents: str, head: str = "") -> str:
    """The text after the fence of a block ``expand`` produced.

    Args:
        contents: the lines between the fences.
        head: the commit ``expand`` ran at (40 hex digits), empty when git could
            not say (keyword: evidence-head, pitboss#398).

    Returns:
        The mark and the digest, and ``head=`` and the head when it is given.
    """
    named = f" {HEAD_KEY}{head}" if head else ""
    return f"{MARK} {DIGEST_KEY}{digest(contents)}{named}"


def recorded_head(text: str) -> str:
    """The head a block's opening line records.

    Args:
        text: the text after the fence.

    Returns:
        The 40 hex digits after ``head=`` at its end; empty when it has none (a
        block made before the head was recorded).
    """
    found = re.search(rf" {HEAD_KEY}([0-9a-f]{{{HEAD_LENGTH}}})$", text)
    return found.group(1) if found else ""


def contents(command: str, outcome: Outcome) -> str:
    """The lines of a block: the command, its output, its status when nonzero.

    The output is never trimmed or filtered, except that a byte order mark and
    carriage returns, which a store drops, are removed (``normalise``). One
    that does not end with a newline gets a line saying so, so the closing
    fence is a line of its own.

    Args:
        command: the command line as written.
        outcome: what it did.

    Returns:
        The lines between the fences.
    """
    printed = normalise(outcome.output)
    ended = printed.endswith("\n") or not printed
    return "".join(
        [
            f"{PROMPT}{command}\n",
            printed,
            "" if ended else "\n" + NO_NEWLINE,
            f"exit status: {outcome.status}\n" if outcome.status else "",
        ]
    )


def block(command: str, outcome: Outcome, head: str = "") -> str:
    """The fenced block of a command.

    Args:
        command: the command line as written.
        outcome: what it did.
        head: the commit the command ran at, recorded in the opening line.

    Returns:
        The block, its fence longer than any run of backticks inside it.
    """
    inside = contents(command, outcome)
    longest = max((len(each) for each in TICKS.findall(inside)), default=0)
    fence = "`" * max(MIN_FENCE, longest + 1)
    return f"{fence}{info(inside, head)}\n{inside}{fence}\n"


# a block `block` produced: the fence, the mark and digest, the lines, the fence
PRODUCED = re.compile(
    rf"^(?P<fence>`{{3,}}){MARK} {DIGEST_KEY}(?P<digest>[0-9a-f]{{{DIGEST_LENGTH}}})"
    rf"(?: {HEAD_KEY}[0-9a-f]{{{HEAD_LENGTH}}})?"
    r"[ \t]*\n(?P<inside>(?:.*\n)*?)(?P=fence)[ \t]*$",
    re.MULTILINE,
)


def _collapsed_block(found: re.Match[str]) -> str:
    inside = found["inside"]
    if inside.startswith(PROMPT) and digest(inside) == found["digest"]:
        return inside.split("\n", 1)[0]
    return found[0]


def collapsed(text: str) -> str:
    """The text with each block ``expand`` produced as its command line.

    What a re-expansion changes (the head, a timing line) is in the output of a
    block and not in its command (keyword: plan-digest-collapse, pitboss#358).

    Args:
        text: any text, a Plan section for one.

    Returns:
        The text in which each fenced block whose opening line carries the digest
        of its contents is its ``$ command`` line alone; a block whose digest is
        not that of its contents (one edited by hand), one with no closing fence
        and every other line are kept as they are.
    """
    return PRODUCED.sub(_collapsed_block, text)


def text_digest(text: str) -> str:
    """The digest of a text that a review records (the one of ``bodydigest.digest``).

    The two modules each hold the code: neither imports the other, because the
    sweep's modules are held to an import depth (keyword: import-depth), and a
    test pins that they agree.

    Args:
        text: the text.

    Returns:
        The first 16 hex digits of the SHA-256 of the text with ``\\n`` line
        endings and no trailing white space.
    """
    plain = re.sub(r"\r\n?", "\n", text).rstrip()
    return hashlib.new("sha256", plain.encode("utf-8")).hexdigest()[:DIGEST_LENGTH]


def run_urls_dropped(text: str) -> str:
    """The text with the run and job ids of each Actions address dropped.

    A CI pointer names the run of the head, and ``plan-check`` rewrites the run and
    job addresses for every head; what the Plan says is the workflow, the job, the
    step and the string, so a change of those ids alone is no edit of the Plan
    (keyword: plan-digest-urls, pitboss#475).

    Args:
        text: any text, a Plan section for one.

    Returns:
        The text in which ``.../actions/runs/ID`` and ``.../actions/runs/ID/job/ID``
        are ``.../actions/runs``.
    """
    return RUN_ADDRESS.sub(r"\1/actions/runs", text)


@functools.cache
def accepted_digests(text: str) -> Sequence[str]:
    """The digests a record of a Plan section may carry to be of this section.

    It is the digest of the section with each block ``expand`` produced collapsed
    to its command (keyword: plan-digest-collapse, pitboss#358) and the run and
    job ids of its Actions addresses dropped (keyword: plan-digest-urls,
    pitboss#475). The second is the digest of the section collapsed only, which
    records made before the ids were dropped carry (it goes with pitboss#475's
    own removal). The digest of the section as it is, which records made before
    the collapse carry, is no longer accepted (pitboss#399).

    Args:
        text: the section, empty when the body has none.

    Returns:
        The two digests; none for no section.
    """
    if not text:
        return []
    return [
        text_digest(run_urls_dropped(collapsed(text))),
        text_digest(collapsed(text)),
    ]


def section_digest(text: str) -> str:
    """The digest a review records for a Plan section.

    Args:
        text: the section, empty when the body has none.

    Returns:
        The first of ``accepted_digests``, empty for no section.
    """
    return next(iter(accepted_digests(text)), "")


def section_changed(recorded: str, text: str) -> bool:
    """Whether a Plan section is no longer the one a review recorded.

    Args:
        recorded: the digest the review records, empty when it records none.
        text: the section now, empty when it is not checked.

    Returns:
        True when both are given and the digest is none of ``accepted_digests``.
    """
    return bool(text and recorded and recorded not in accepted_digests(text))


def _command_of(line: str, number: int) -> str:
    command = line[len(PROMPT) :].rstrip("\r\n")
    if not command.strip():
        raise TemplateError(f"line {number}: a directive line has no command")
    return command


def _expand_line(shell: Shell, head: str, number: int, line: str) -> str:
    if line.startswith(ESCAPED_PROMPT):
        return PROMPT + line[len(ESCAPED_PROMPT) :]
    if not line.startswith(PROMPT):
        return line
    command = _command_of(line, number)
    return block(command, shell(command), head)


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


def expand(template: str, shell: Shell, head: str = "") -> str:
    """Fill in a template.

    Every line of the template that is not a directive is kept as it is; a
    line that starts with ``\\$ `` is kept with the backslash removed. The
    commands are checked first, so a template with a bad directive runs
    nothing.

    Args:
        template: the template's text.
        shell: runs one command line.
        head: the commit the commands run at, written in each block's opening
            line (keyword: evidence-head, pitboss#398); none records none.

    Returns:
        The body.
    """
    commands(template)
    return "".join(
        _expand_line(shell, head, number, line)
        for number, line in enumerate(template.splitlines(keepends=True), 1)
    )
