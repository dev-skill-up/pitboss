"""The Plan's Done-when is the ticket's, word for word (keyword: plan-done-when).

Seen on pitboss#378 (pitboss#317): an "Interpretation" paragraph in the Execution
narrowed Done-when items 5 to 7, and a review found it a round later.
``pitboss plan-check`` reads the ticket and its comments and refuses a Plan that
does not hold, word for word, every line of the ticket's Done-when and of each
``Added to the Done-when`` comment, naming the first line that differs
(``plan-done-when``). It also refuses a body whose Plan or Execution has an
"Interpretation" or "interpreted" paragraph about a Done-when item
(``plan-interpretation``): an item that cannot be met as written is NOT PROCEEDING,
with the evidence. The module reads nothing: the texts are given.
"""

import re
from typing import Sequence

from . import bodytext, ticketwhen

CHECK = "plan-done-when"
INTERPRETATION = "plan-interpretation"
SHOWN = 100
INTERPRET = re.compile(r"\binterpret(?:ation|ations|ed|ing|s)?\b", re.IGNORECASE)
ABOUT = re.compile(r"\bdone[- ]when\b|\bitems?\s+\d", re.IGNORECASE)


def _squeezed(text: str) -> str:
    return " ".join(text.split())


def findings(section: str, ticket: str, comments: Sequence[str]) -> Sequence[str]:
    """The first line of the ticket's Done-when that the Plan does not hold.

    Args:
        section: the Plan section.
        ticket: the ticket's text.
        comments: the ticket's comments, oldest first.

    Returns:
        One finding naming the first line, and where it comes from, that is not
        in the Plan word for word (whitespace and line breaks aside); none when
        the Plan holds them all.
    """
    plan = _squeezed(section)
    for source, line in ticketwhen.expected(ticket, comments):
        if _squeezed(line) not in plan:
            return [
                f"{CHECK}: the Plan's Done-when is not {source} word for word;"
                f" the first line that differs is: {line[:SHOWN]}"
            ]
    return []


def interpretations(body: str) -> Sequence[str]:
    """The paragraphs of the Plan and the Execution that interpret a Done-when item.

    Args:
        body: the PR's body.

    Returns:
        A finding for each paragraph (outside a fenced block) that has the word
        "interpretation", "interpreted" or the like and names a Done-when or an
        item number.
    """
    return [
        f"{INTERPRETATION}: a paragraph interprets a Done-when item"
        f" ({_squeezed(each)[:SHOWN]}): an item that cannot be met as written is"
        " NOT PROCEEDING, with the evidence; the Plan does not narrow it"
        for each in bodytext.paragraphs(body)
        if INTERPRET.search(each) and ABOUT.search(each)
    ]
