"""Split a body over the store's limit into comments (keyword: expand-split, #177).

A PR body over the store's limit (65536 characters) breaks, and the footer is
lost. ``pitboss expand --pr`` cuts the expanded text into parts on paragraph
markers (a blank line outside a fence, the end of a block ``expand`` produced),
never inside a block when a block fits a part. Part 1 stays the description,
with the closing paragraph (the footer) after a section that cites every later
part by its URL; the later parts are comments that start with ``MARKER``, which
a rerun finds and rewrites instead of adding more.
"""

import dataclasses
import re
from typing import Callable, Sequence

LIMIT = 65536
MARKER = "<!-- pitboss-expand-part "
HEADER_ROOM = 100
URL_ROOM = 200
MIN_ROOM = 1000
TAIL_SHARE = 4
HEADING = "## Evidence in comments"
OVERFLOW = (
    "Overflowed to comments, as per the standing decision: {count} parts past the"
    " {limit}-character limit, split by pitboss, not an accident"
)
FENCE = re.compile(r"^(`{3,})")
ROW = re.compile(r"^`{3,}pitboss-expand [^\n]*\n\$ ([^\n]*)", re.MULTILINE)


class TooLong(ValueError):  # noqa: SLD504,SLD401
    """A body that cannot be made to fit."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Comment:
    """A comment of the pull request.

    Attributes:
        number: the comment's id.
        url: its address.
        body: its text.
    """

    number: int
    url: str
    body: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Store:
    """One pull request and its comments, as the store keeps them.

    Attributes:
        comments: lists the comments, oldest first.
        post: adds a comment of a text and gives it back.
        edit: replaces the text of the comment of an id and gives it back.
        delete: removes the comment of an id.
        set_body: replaces the description.
    """

    comments: Callable[[], Sequence[Comment]]
    post: Callable[[str], Comment]
    edit: Callable[[int, str], Comment]
    delete: Callable[[int], None]
    set_body: Callable[[str], None]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Divided:
    """A body cut into its parts.

    Attributes:
        head: part 1, the start of the description.
        tail: the closing paragraph, kept in the description.
        later: the later parts (parts 2 and on), each for a comment.
    """

    head: str
    tail: str
    later: Sequence[str]


def after(line: str, fence: str) -> tuple[bool, str]:
    """Say whether a line ends a paragraph, and which fence is open after it.

    Args:
        line: the line, with its newline.
        fence: the fence that is open before it; empty outside a block.

    Returns:
        Whether a paragraph ends with the line, and the open fence.
    """
    bare = line.rstrip("\r\n")
    if fence:
        return bare == fence, "" if bare == fence else fence
    opening = FENCE.match(bare)
    return (not opening and not bare.strip()), opening.group(1) if opening else ""


def units(text: str) -> Sequence[str]:
    """Cut text after each paragraph marker.

    A marker is a blank line outside a fence, or the closing fence of a block.

    Args:
        text: the text.

    Returns:
        The pieces, which join to the text.
    """
    found: list[str] = []
    current = ""
    fence = ""
    for line in text.splitlines(keepends=True):
        current += line
        ended, fence = after(line, fence)
        if ended:
            found.append(current)
            current = ""
    return [*found, current] if current else found


def cut(unit: str, room: int) -> Sequence[str]:
    """Cut a piece longer than a part on line ends, or inside a line if it must.

    Args:
        unit: the piece.
        room: the most characters of a part.

    Returns:
        The pieces, each of at most ``room`` characters, which join to the piece.
    """
    lines = unit.splitlines(keepends=True)
    chunks = [
        line[at : at + room] for line in lines for at in range(0, len(line), room)
    ]
    return [each for each in pack(chunks, room, room) if each]


def pack(pieces: Sequence[str], first: int, others: int) -> Sequence[str]:
    """Fill the parts in order, each as full as the paragraphs allow.

    Args:
        pieces: the pieces, none longer than ``first`` or ``others``.
        first: the room of the first part.
        others: the room of every other part.

    Returns:
        The parts.
    """
    found: list[str] = [""]
    for each in pieces:
        room = first if len(found) == 1 else others
        if found[-1] and len(found[-1]) + len(each) > room:
            found.append("")
        found[-1] += each
    return found


def citations(
    later: Sequence[str], addresses: Sequence[str], limit: int = LIMIT
) -> str:
    """The section that cites every later part and each row in it.

    Args:
        later: the later parts.
        addresses: the URL of each.
        limit: the most characters of a body or a comment.

    Returns:
        The section, whose first line says that the overflow is by design
        (pitboss#317).
    """
    total = len(later) + 1
    lines = [
        HEADING,
        "",
        OVERFLOW.format(count=len(later), limit=limit) + ".",
        "",
        "Part 1 is this description; the later parts are comments.",
    ]
    for number, (text, address) in enumerate(zip(later, addresses), 2):
        lines.extend(["", f"Part {number} of {total}: {address}"])
        lines.extend(
            f"- row `{each}`: part {number}, {address}" for each in ROW.findall(text)
        )
    return "\n".join(lines) + "\n"


def joined(head: str, cited: str, tail: str) -> str:
    """Put the citations between the head and the closing paragraph.

    Args:
        head: part 1.
        cited: the citations.
        tail: the closing paragraph.

    Returns:
        The description.
    """
    return f"{head.rstrip(chr(10))}\n\n{cited}" + (f"\n{tail}" if tail else "")


def closing(pieces: Sequence[str], limit: int) -> tuple[Sequence[str], str]:
    """Take the closing paragraph off the pieces, when it is the footer's kind.

    Args:
        pieces: the pieces.
        limit: the most characters of a body.

    Returns:
        The pieces without the last one and the last one, when it holds no
        block and is a small part of the limit; otherwise all the pieces and
        nothing.
    """
    last = pieces[-1]
    if "```" in last or len(last) * TAIL_SHARE > limit:
        return pieces, ""
    return pieces[:-1], last


def fitted(pieces: Sequence[str], tail: str, limit: int) -> Divided:
    """Find the cut whose description with its citations fits.

    Args:
        pieces: the pieces without the closing paragraph.
        tail: the closing paragraph.
        limit: the most characters of a body or a comment.

    Returns:
        The cut.

    Raises:
        TooLong: when the citations leave no room for the description.
    """
    reserve = 0
    while True:
        first = limit - len(tail) - reserve
        others = limit - HEADER_ROOM
        if first < MIN_ROOM:
            raise TooLong(f"the body cannot be cut to {limit} characters")
        cuts = [each for unit in pieces for each in cut(unit, min(first, others))]
        parts = pack(cuts, first, others)
        cited = citations(parts[1:], ["x" * URL_ROOM] * len(parts[1:]), limit)
        if len(joined(parts[0], cited, tail)) <= limit:
            return Divided(head=parts[0], tail=tail, later=parts[1:])
        reserve = max(reserve + 1, len(cited))


def divide(text: str, limit: int = LIMIT) -> Divided:
    """Cut a body into the description and the comments.

    Args:
        text: the expanded body.
        limit: the most characters of a body or a comment.

    Returns:
        The parts; none later when the text fits.
    """
    if len(text) <= limit:
        return Divided(head=text, tail="", later=())
    pieces, tail = closing(units(text), limit)
    return fitted(pieces, tail, limit)


def comment_body(text: str, number: int, total: int) -> str:
    """The text of a comment.

    Args:
        text: the part.
        number: its number among the parts (2 and on).
        total: how many parts there are.

    Returns:
        The marker line and the part.
    """
    return f"{MARKER}{number} of {total} -->\n\n{text}"


def write(store: Store, cut_up: Divided) -> Sequence[str]:
    """Write the later parts as comments, the earlier ones first.

    The comments an earlier run made are rewritten in order, the ones a shorter
    body no longer needs are removed, and a longer body adds the rest, so a
    rerun leaves as many comments as the body needs.

    Args:
        store: the pull request's store.
        cut_up: the cut body.

    Returns:
        The URL of each later part.
    """
    own = [each for each in store.comments() if each.body.startswith(MARKER)]
    total = len(cut_up.later) + 1
    addresses: list[str] = []
    for index, text in enumerate(cut_up.later):
        body = comment_body(text, index + 2, total)
        if index < len(own):
            addresses.append(store.edit(own[index].number, body).url)
        else:
            addresses.append(store.post(body).url)
    for each in own[len(cut_up.later) :]:
        store.delete(each.number)
    return addresses


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Applied:
    """A body put in a pull request.

    Attributes:
        body: the description as set.
        notice: what ``pitboss expand`` says on standard error: empty when the
            body fitted, else that the overflow is by design and the URL of each
            comment (pitboss#317).
    """

    body: str
    notice: str


def notice(count: int, limit: int, addresses: Sequence[str]) -> str:
    """The text that says the overflow is the standing decision, with its URLs.

    Args:
        count: how many parts went to comments.
        limit: the most characters of a body or a comment.
        addresses: the URL of each comment.

    Returns:
        The sentence, then a line for each comment's part and URL.
    """
    lines = [OVERFLOW.format(count=count, limit=limit) + ", URLs below"]
    lines.extend(
        f"part {n} of {count + 1}: {each}" for n, each in enumerate(addresses, 2)
    )
    return "\n".join(lines) + "\n"


def applied(store: Store, text: str, limit: int = LIMIT) -> Applied:
    """Put a body in a pull request, the later parts in comments.

    Args:
        store: the pull request's store.
        text: the expanded body.
        limit: the most characters of a body or a comment.

    Returns:
        The description as set, and the notice of an overflow.

    Raises:
        TooLong: when the description with its citations is over the limit.
    """
    cut_up = divide(text, limit)
    addresses = write(store, cut_up)
    cited = citations(cut_up.later, addresses, limit)
    final = joined(cut_up.head, cited, cut_up.tail) if cut_up.later else text
    if len(final) > limit:
        raise TooLong(f"the description is {len(final)} characters, over {limit}")
    store.set_body(final)
    said = notice(len(cut_up.later), limit, addresses) if cut_up.later else ""
    return Applied(body=final, notice=said)


def apply(store: Store, text: str, limit: int = LIMIT) -> str:
    """Put a body in a pull request, the later parts in comments.

    Args:
        store: the pull request's store.
        text: the expanded body.
        limit: the most characters of a body or a comment.

    Returns:
        The description as set.
    """
    return applied(store, text, limit).body
