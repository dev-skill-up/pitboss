"""Whether a PR's body has a Plan and an Execution (keyword: review-flow)."""

import re

_PLAN_HEADING = re.compile(r"^## Plan\s*$", re.MULTILINE)
_EXECUTION_HEADING = re.compile(r"^## Execution\s*$", re.MULTILINE)
_PLACEHOLDER = re.compile(
    r"^[\W_]*(not\s+(yet\s+)?(started|written|done)|to\s+be\s+(written|filled)"
    r"|todo|to\s+do|tbd|written\s+after)(?![^\W_])",
    re.IGNORECASE,
)


def has_plan_execution_body(body: str) -> bool:
    """Whether a PR body has a Plan section and an Execution section.

    Args:
        body: the PR's body.

    Returns:
        True when both headings (``## Plan``, ``## Execution``) are there.
    """
    return bool(_PLAN_HEADING.search(body) and _EXECUTION_HEADING.search(body))


def execution_unwritten(body: str) -> bool:
    """Whether the Execution section of a PR body is empty or a placeholder.

    A placeholder is a first line that says the work is not done yet
    (``Not started: it is written after the Plan is approved``, ``TBD``): no
    reviewer can grade it (keyword: unwritten-execution, pitboss#294).

    Args:
        body: the PR's body.

    Returns:
        True when the body has an Execution heading and the text under it, up
        to the next ``## `` heading, is empty or starts as a placeholder.
    """
    after = iter(body.splitlines())
    if not any(_EXECUTION_HEADING.match(text) for text in after):
        return False
    written = []
    for text in after:
        if text.startswith("## "):
            break
        written.append(text)
    first = next((each.strip() for each in written if each.strip()), "")
    return not first or bool(_PLACEHOLDER.match(first))


_CI_QUOTE = re.compile(r"\bCI\s+quotes?\b", re.IGNORECASE)
_QUOTE_LINE = re.compile(r"^[\W_]*CI\s+quotes?\b", re.IGNORECASE)


def _section(body: str, heading: "re.Pattern[str]") -> list[str]:
    lines = iter(body.splitlines())
    if not any(heading.match(text) for text in lines):
        return []
    found = []
    for text in lines:
        if text.startswith("## "):
            break
        found.append(text)
    return found


def ci_quotes_missing(body: str) -> bool:
    """Whether the Plan has CI-quote rows and the Execution fewer quotes.

    A CI-quote row is a line of the Plan that names a ``CI quote``; a quote in
    the Execution is a line that starts with ``CI quote`` (a list mark or bold
    before it is allowed). The Plan puts the quotes after CI exists, so the
    review of the Execution waits for them (keyword: ci-quotes, pitboss#277).

    Args:
        body: the PR's body.

    Returns:
        True when the Plan names more CI quotes than the Execution gives.
    """
    rows = sum(1 for each in _section(body, _PLAN_HEADING) if _CI_QUOTE.search(each))
    quoted = _section(body, _EXECUTION_HEADING)
    return sum(1 for each in quoted if _QUOTE_LINE.match(each)) < rows
