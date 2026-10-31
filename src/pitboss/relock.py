"""Which pull requests are relock pull requests (keyword: relock, pitboss#126).

The daily relock opens a pull request from a branch whose name starts with a
configured prefix (``[relock] prefix``, default ``relock/``). It fixes no
ticket and has no hand-written Plan or Execution, so the sweep and the body
lint treat it apart: it goes straight to its review.
"""


def is_relock(branch: str, prefix: str) -> bool:
    """Whether a head branch is a relock branch.

    Args:
        branch: the PR's head branch.
        prefix: the configured prefix; an empty one names no relock branch.

    Returns:
        True when the branch starts with the prefix.
    """
    return bool(prefix) and branch.startswith(prefix)
