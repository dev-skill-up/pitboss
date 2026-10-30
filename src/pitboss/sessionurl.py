"""The harness's session URL, which every reader of a body or comment ignores.

The harness tells every agent to end a PR description with a line holding
``https://claude.ai/code/session_...``, and the generated-by footer's link can
carry the same suffix. Owner ruling (dev-skill-up/pitboss#109): such a line and
such a suffix are absent for every parser (keyword: session-url).
"""

import re

URL_LINE = re.compile(
    r"^[ \t]*<?https://claude\.ai/code/session_[\w-]+>?[ \t]*\r?\n?", re.M
)
URL_SUFFIX = re.compile(r"(\]\(https://claude\.(?:ai|com)/code)/session_[\w-]+(?=\))")


def strip(text: str) -> str:
    """Remove the session URL from a PR body or a comment.

    Args:
        text: the body or comment.

    Returns:
        The text without each line that is only a session URL and without the
        ``/session_...`` suffix of a Markdown link's address; a session URL
        inside prose is kept.
    """
    return URL_SUFFIX.sub(r"\1", URL_LINE.sub("", text))
