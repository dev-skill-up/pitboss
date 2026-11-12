"""The owner's call is labelled ``paused-owner`` at that moment (keyword: owner-pause).

Owner, 2026-11-11 22:34Z: a PR that waits for the owner carries the label and the
question, and is never reported as "nothing needed from you" (A5, pitboss#444).
``pitboss owner-pause`` puts the label and posts the question; this module says
whether the question is one: it names the options and has the ``How we got here``
section (``analysis``). It reads nothing: the question is given.
"""

from . import analysis

NO_OPTIONS = "the question names no options: a line that starts with `Options`"
NO_SECTION = f"no `{analysis.SECTION}` section with the analysis in it"


def refusal(question: str) -> str:
    """Say why a question may not pause a PR.

    Args:
        question: the text posted for the owner.

    Returns:
        The reason, or an empty string when the text names the options (a line
        that starts with ``Options``) and has a ``How we got here`` section.
    """
    if not any(
        each.lstrip("#* \t").startswith("Options") for each in question.splitlines()
    ):
        return NO_OPTIONS
    return "" if analysis.has_section(question) else NO_SECTION


def label_path(slug: str, number: int) -> str:
    """The API path that adds labels to a PR.

    Args:
        slug: the repository's ``owner/name``.
        number: the PR's number.

    Returns:
        The path under ``https://api.github.com/``; the label is
        ``steps.PAUSED_LABEL``.
    """
    return f"repos/{slug}/issues/{number}/labels"
