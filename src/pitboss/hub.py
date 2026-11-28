"""The edge: GitHub over ``gh api`` (REST, every list paginated). The only I/O."""

import json
import subprocess
from typing import Any, Sequence


def get(path: str) -> Any:
    """Read one REST path, every page.

    Args:
        path: the path under the API root.

    Returns:
        The decoded JSON, the pages of a list joined.
    """
    out = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", path],
        check=True, capture_output=True, text=True,
    ).stdout
    pages = json.loads(out)
    if pages and isinstance(pages[0], dict) and "check_runs" in pages[0]:
        return [run for page in pages for run in page["check_runs"]]
    if pages and isinstance(pages[0], list):
        return [item for page in pages for item in page]
    return pages[0] if pages else None


def send(method: str, path: str, fields: Sequence[str] = ()) -> None:
    """Write one REST call.

    Args:
        method: the HTTP method.
        path: the path under the API root.
        fields: ``key=value`` body fields.
    """
    args = ["gh", "api", "-X", method, path]
    for field in fields:
        args += ["-f", field]
    subprocess.run(args, check=True, capture_output=True, text=True)


class Gh:
    """The writes of ``actions.Hub`` for one repository."""

    def __init__(self, repo: str) -> None:
        self.repo = repo

    def merge(self, number: int) -> None:
        send("PUT", f"repos/{self.repo}/pulls/{number}/merge", ["merge_method=merge"])

    def undraft(self, number: int) -> None:
        node = get(f"repos/{self.repo}/pulls/{number}")["node_id"]
        subprocess.run(
            ["gh", "api", "graphql", "-f", f"id={node}", "-f",
             "query=mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){clientMutationId}}"],
            check=True, capture_output=True, text=True,
        )

    def comment(self, number: int, body: str) -> None:
        send("POST", f"repos/{self.repo}/issues/{number}/comments", [f"body={body}"])
