"""Records with every field written out, which a witness or a test changes (one-path).

The records of the World's closure have no field default (plan 6.1, P3; keyword:
one-path), so what sets a few fields starts from one of these.
"""

import dataclasses

from . import shapes

GRADED = shapes.Graded(
    sha="",
    when="",
    plan=None,
    execution=None,
    comment=True,
    body="",
    missed=0,
    plan_digest="",
)
CHECK_RUN = shapes.CheckRun(
    id=0,
    name="",
    finished=False,
    failed=False,
    head_sha="",
    started_at="",
    completed_at="",
    run=0,
    succeeded=False,
    said=("", ""),
)
COMMENT = shapes.Comment(
    body="", author_association="", created_at="", url="", login=""
)


def member_comment(body: str, when: str, url: str = "") -> shapes.Comment:
    """A comment a member of the organisation wrote.

    Args:
        body: its text.
        when: when it was written (ISO 8601).
        url: its address.

    Returns:
        The comment.
    """
    return dataclasses.replace(
        COMMENT, body=body, author_association="MEMBER", created_at=when, url=url
    )
