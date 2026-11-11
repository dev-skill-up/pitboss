"""The form of an Opus ruling file that ``ruling post`` posts (pitboss#466)."""

from . import analysis, flowstate, rulingwords, sessionurl

NO_WORD = "the second line is not `Ruling: <word>` with a word of: "


def refusal(text: str) -> str:
    """Say why a ruling file may not be posted.

    Args:
        text: the file.

    Returns:
        The reason, or an empty string when the file is a ruling in the form
        pitboss reads: a first line ``Opus ruling``, a second line ``Ruling:``
        and a word of ``rulingwords.Ruling``, and a ``How we got here`` section.
    """
    if not flowstate.is_ruling(text):
        return "the first line is not exactly `Opus ruling`"
    if flowstate.read_ruling(text) is None:
        second = "".join(sessionurl.lines(text)[1:2]).rstrip()
        return f"{NO_WORD}{rulingwords.WORDS} (it is {second!r})"
    if not analysis.has_section(text):
        return f"no `{analysis.SECTION}` section with the analysis in it"
    return ""
