"""The fixed prompt for what needs judgement, filled with the gathered facts."""

from typing import Sequence

from .redshapes import RedClass

TEMPLATE = """\
You analyse one red run of the workflow {workflow} in {repo}. You are \
read-only on GitHub: change nothing there. Tie every claim to a run id, job \
id, log line, commit, comment id or transcript line, as a link. Never call a \
failure a flake: say the mechanism, or say the cause is not established. If \
you infer this run's cause from another identical run, say so and name that \
run.

Facts the tool gathered (they are fixed; do not recompute them):
{facts}

Do these steps, in order, and answer each in one short paragraph:
1. Cause. Say "established" and name what establishes it (a fix commit's \
message and file list, a ticket, a log line), or say "not established" and \
name what you looked at.
2. Local runs. Read the transcript named above (or say it was not found) and \
state what the pushing worker ran locally before the push, and whether the \
failing test or fixture was among those runs.
3. Detector. Say who detected the red (CI, the queue, the orchestrator's \
sweep, a human) and when, from the comments on the PR and the tickets.
4. First detector that could have caught it, with its cost: a short check \
before push, a workflow edge, running the test under CI's conditions, or \
"nothing: the registry was down". Do not propose a check that costs more than \
CI took to show the failure.
5. Fix verification. Say whether the fix merged on one green run, on a repeat, \
or on nothing (the next run was a merge of main). If the failure is a timing \
race, one green run is not evidence: say so.
6. Class. Confirm the class above, or replace it with one of: {classes}. \
Choose by the first cause named.
"""


def facts_block(lines: Sequence[str]) -> str:
    """Join fact lines into the block the prompt carries.

    Args:
        lines: the facts, one per line, each with its links.

    Returns:
        The block.
    """
    return "\n".join(line if line.startswith("  ") else f"- {line}" for line in lines)


def fill(workflow: str, repo: str, facts: Sequence[str]) -> str:
    """Fill the prompt with a run's facts.

    Args:
        workflow: the workflow.
        repo: the repository's ``owner/name``.
        facts: the facts, one per line.

    Returns:
        The prompt.
    """
    return TEMPLATE.format(
        workflow=workflow,
        repo=repo,
        facts=facts_block(facts),
        classes="; ".join(each.value for each in RedClass),
    )
