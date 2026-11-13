"""A fake PR's details with every field GitHub's schema requires (keyword: gate).

The worlds can a PR as ``fakes.pull_body`` makes it; the fake API answers a PR's
details with the fields a test does not set added, as GitHub gives them, so the
gate rows read the PR as they read GitHub's.
"""

import re
from typing import Mapping

DETAILS = re.compile(r"^repos/([^/]+/[^/]+)/pulls/(\d+)$")


def complete(path: str, body: object) -> object:
    """A canned body, the details of a PR completed.

    Args:
        path: the path asked for.
        body: what the world cans for it.

    Returns:
        The body; a PR's details with every required field.
    """
    found = DETAILS.match(path)
    if found is None or not isinstance(body, Mapping) or "number" not in body:
        return body
    return _completed(body, found.group(1))


FIXED: Mapping[str, object] = {
    "_links": {},
    "author_association": "MEMBER",
    "closed_at": None,
    "merged": False,
    "merged_by": None,
    "mergeable": True,
    "milestone": None,
    "labels": [],
    "locked": False,
    "maintainer_can_modify": False,
    "comments": 0,
    "review_comments": 0,
    "commits": 1,
    "additions": 0,
    "deletions": 0,
    "changed_files": 0,
}
# each URL field: the API's path under the repository, or the page's suffix
API_PATHS = {
    "url": "pulls/{n}",
    "issue_url": "issues/{n}",
    "comments_url": "issues/{n}/comments",
    "commits_url": "pulls/{n}/commits",
    "review_comments_url": "pulls/{n}/comments",
    "review_comment_url": "pulls/comments{{/number}}",
    "statuses_url": "statuses/{n}",
}
PAGE_SUFFIXES = {"html_url": "", "diff_url": ".diff", "patch_url": ".patch"}


def _urls(slug: str, number: object) -> Mapping[str, object]:
    # the URL fields of the PR
    api = f"https://api.github.com/repos/{slug}/"
    page = f"https://github.com/{slug}/pull/{number}"
    found = {name: api + path.format(n=number) for name, path in API_PATHS.items()}
    found.update({name: page + end for name, end in PAGE_SUFFIXES.items()})
    return found


def _completed(body: Mapping[str, object], slug: str) -> Mapping[str, object]:
    # the fields a test does not set, as GitHub gives them for this PR
    number = body["number"]
    found: dict[str, object] = {
        **FIXED,
        **_urls(slug, number),
        "id": number,
        "node_id": f"PR_{number}",
        "updated_at": body.get("created_at"),
        **body,
    }
    for side in ("base", "head"):
        branch = found.get(side)
        if isinstance(branch, Mapping):
            found[side] = {"repo": {"full_name": slug}, **branch}
    return found


# the fields of a PR that its row of the open listing carries too
ROW_FIELDS = ("title", "body", "head", "draft", "created_at", "user")


def row_fields(changes: Mapping[str, object]) -> Mapping[str, object]:
    """The changes to a PR that its row of the open listing carries too.

    Args:
        changes: changes to the PR's JSON.

    Returns:
        The ones the listing's row has.
    """
    return {key: value for key, value in changes.items() if key in ROW_FIELDS}
