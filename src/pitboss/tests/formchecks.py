"""Helpers the tests of the form checks share."""

import re
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import evidence, forms
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


def body_checks(body: str, head: str = HEAD) -> Sequence[str]:
    """The checks a PR body fails.

    Args:
        body: the body.
        head: the head given.

    Returns:
        The failed checks' names.
    """
    return checks(forms.pr_body(subject(body, head)))


def findings(body: str) -> Sequence[str]:
    """The findings on a PR body.

    Args:
        body: the body.

    Returns:
        Each finding, as the lint prints it.
    """
    return forms.pr_body(subject(body))


def typed_at(text: str, rows: Sequence[int]) -> None:
    """Assert the lines of a body that are refused as hand-typed rows.

    Args:
        text: the body.
        rows: the line numbers refused.
    """
    assert_that(evidence.hand_typed(text), equal_to(list(rows)))
