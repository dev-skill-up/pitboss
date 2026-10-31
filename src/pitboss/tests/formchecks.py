"""Helpers the tests of the form checks share."""

import re
from typing import Sequence

from .. import forms
from .linting import HEAD


def checks(found: Sequence[str]) -> Sequence[str]:
    """The names of the checks that found something.

    Args:
        found: the findings.

    Returns:
        Each finding's check name, in order.
    """
    return [re.findall(r"\(([a-z-]+)\)$", each)[0] for each in found]


def subject(body: str, head: str = HEAD) -> forms.Subject:
    """A text to check.

    Args:
        body: its text.
        head: the head given.

    Returns:
        The subject.
    """
    return forms.Subject(name="text", body=body, head=head)


def body_checks(
    body: str, head: str = HEAD, footers: Sequence[str] = ()
) -> Sequence[str]:
    """The checks a PR body fails.

    Args:
        body: the body.
        head: the head given.
        footers: the footers required (none by default).

    Returns:
        The failed checks' names.
    """
    return checks(forms.pr_body(subject(body, head), footers))


def findings(body: str) -> Sequence[str]:
    """The findings on a PR body, with no footer required.

    Args:
        body: the body.

    Returns:
        Each finding, as the lint prints it.
    """
    return forms.pr_body(subject(body), ())
