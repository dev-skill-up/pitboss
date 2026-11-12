"""The verbs that change a PR's state or the project's holds (keyword: act-verbs).

merge, arm and undraft run the verdict in the same call as the write; arm
records the head it armed; hold disarms and dequeues the PRs it covers; label
``paused-owner`` and block disarm the PR; override lifts one stop line at one
head, never a failed check or status, a hold, a block, a closed PR or a failed
read.
"""

from . import totalanswer
from .actcore import (
    DISARMING,
    HOLD_LABEL,
    Act,
    Change,
    Options,
    Refused,
    Target,
    gate,
    head_of,
    option,
    record,
    verdict_of,
)
from .totaljson import text

LABELS = totalanswer.KNOWN_LABELS | {"p0", "p1", "p2", "p3", HOLD_LABEL}
WORKFLOWS = ("relock.yml", "check.yml")
CLOSE_REASONS = ("completed", "not_planned", "duplicate")
OVERRIDDEN = ("merge", "arm", "undraft")


def _gated_write(act: Act, action: str, target: Target) -> str:
    gate(act, action, target.repo)
    pull = verdict_of(act, action, target)
    if action == "arm":
        record(act, target, f"arm head={head_of(pull)}")
    act.hub.write(Change(kind=action, repo=target.repo, number=target.number))
    return f"{action} {target.repo}#{target.number} at {head_of(pull)}"


def merge(act: Act, target: Target, options: Options) -> str:
    """Merge a PR when the verdict is GO.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    return _gated_write(act, "merge", target)


def arm(act: Act, target: Target, options: Options) -> str:
    """Arm auto-merge when the verdict is GO, with a record of the head.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    return _gated_write(act, "arm", target)


def undraft(act: Act, target: Target, options: Options) -> str:
    """Mark a draft ready when the verdict is GO.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    return _gated_write(act, "undraft", target)


def disarm(act: Act, target: Target, options: Options) -> str:
    """Disarm auto-merge.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    gate(act, "disarm", target.repo)
    act.hub.write(Change(kind="disarm", repo=target.repo, number=target.number))
    return f"disarm {target.repo}#{target.number}"


def override(act: Act, target: Target, options: Options) -> str:
    """Lift one stop line for the PR's head, with a reason.

    Args:
        act: the verb's world.
        target: the PR.
        options: ``stop`` (the line) and ``reason`` (the ruling it rests on).

    Returns:
        What was done.

    Raises:
        Refused: the line is one no override lifts.
    """
    gate(act, "override", target.repo)
    stop, reason = option(options, "stop"), option(options, "reason")
    if stop.startswith(tuple(act.controls.not_overridable)):
        raise Refused(
            "a hold, a failed check or status, a block, a read failure or a closed PR"
            " is not overridable"
        )
    pull = act.hub.pull(target.repo, target.number)
    ctx = act.inputs(
        target.repo, target.number, pull, act.hub.timeline(target.repo, target.number)
    )
    if not any(
        stop in act.controls.verdict(each, pull, ctx).lines for each in OVERRIDDEN
    ):
        raise Refused(f"not a stop line of this head: {stop[:60]!r}")
    head = head_of(pull)
    record(act, target, f'override head={head} stop="{stop}" reason="{reason}"')
    return f"override {target.repo}#{target.number} at {head}"


def block(act: Act, target: Target, options: Options) -> str:
    """Record that a PR waits on another item; the verdict reads it.

    Args:
        act: the verb's world.
        target: the PR.
        options: ``on`` (``owner/name#N``).

    Returns:
        What was done.
    """
    gate(act, "block", target.repo)
    on = option(options, "on")
    act.controls.disarm(act, target, f"blocked by {on}")
    head = head_of(act.hub.pull(target.repo, target.number))
    record(act, target, f"blocked-by head={head} {on}")
    return f"block {target.repo}#{target.number} on {on}"


def label(act: Act, target: Target, options: Options) -> str:
    """Add or remove a label pitboss applies; ``paused-owner`` disarms.

    Args:
        act: the verb's world.
        target: the PR or issue.
        options: ``name``, and ``remove`` to remove it.

    Returns:
        What was done.

    Raises:
        Refused: a label pitboss does not apply.
    """
    gate(act, "label", target.repo)
    name = option(options, "name")
    if name not in LABELS:
        raise Refused(f"label {name} is not one pitboss applies")
    removing = bool(options.get("remove"))
    if name == totalanswer.PAUSED and not removing:
        act.controls.disarm(act, target, totalanswer.PAUSED)
    kind = "unlabel" if removing else "label"
    act.hub.write(
        Change(kind=kind, repo=target.repo, number=target.number, fields={"name": name})
    )
    return f"{kind} {name} on {target.repo}#{target.number}"


def hold(act: Act, target: Target, options: Options) -> str:
    """Hold a scope in one repository or all; disarm and dequeue the PRs it covers.

    Args:
        act: the verb's world.
        target: the repository ("all" for every one of the project).
        options: ``scope`` (pushes, merges, undrafts, ci, dispatch, all) and
            ``source`` (the owner message it comes from).

    Returns:
        What was done.
    """
    gate(act, "hold", target.repo)
    return make_hold(
        act, target.repo, option(options, "scope"), option(options, "source")
    )


def make_hold(act: Act, where: str, scope: str, source: str) -> str:
    """Make the hold issues and disarm and dequeue what the scope covers.

    Args:
        act: the verb's world.
        where: the repository, or "all".
        scope: the scope held.
        source: the owner message it comes from.

    Returns:
        What was done.
    """
    repos = act.repos if where == "all" else [where]
    for repo in repos:
        fields = {
            "title": f"pitboss hold: {scope}",
            "body": f"scope={scope}\nfrom={source}",
            "labels": HOLD_LABEL,
        }
        act.hub.write(Change(kind="issue", repo=repo, fields=fields))
        for pull in act.hub.open_pulls(repo) if scope in DISARMING else ():
            number = pull.get("number")
            act.controls.disarm(
                act,
                Target(repo=repo, number=number if isinstance(number, int) else 0),
                f"hold {scope}",
            )
    return f"hold {scope} in {', '.join(repos)}"


def unhold(act: Act, target: Target, options: Options) -> str:
    """End a hold (close its issue).

    Args:
        act: the verb's world.
        target: the hold's issue.
        options: none.

    Returns:
        What was done.
    """
    gate(act, "unhold", target.repo)
    act.hub.write(
        Change(
            kind="close-issue",
            repo=target.repo,
            number=target.number,
            fields={"reason": "completed"},
        )
    )
    return f"unhold {target.repo}#{target.number}"


def update_branch(act: Act, target: Target, options: Options) -> str:
    """Merge the base into a PR's branch on GitHub.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    gate(act, "update-branch", target.repo)
    act.controls.disarm(act, target, "the branch is updated")
    act.hub.write(Change(kind="update-branch", repo=target.repo, number=target.number))
    return f"update-branch {target.repo}#{target.number}"


def rerun(act: Act, target: Target, options: Options) -> str:
    """Re-run a run's failed jobs, only for a cause of kind runner.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``run``, ``cause`` (``runner``) and ``evidence`` (the annotation).

    Returns:
        What was done.

    Raises:
        Refused: the cause is not the runner; a red of the code is fixed by a push.
    """
    gate(act, "rerun", target.repo)
    run = option(options, "run")
    if options.get("cause") != "runner" or not options.get("evidence"):
        raise Refused(
            "a re-run needs a cause of kind runner with its evidence (the job's"
            " annotation)"
        )
    act.hub.write(Change(kind="rerun", repo=target.repo, fields={"run": run}))
    return f"rerun {target.repo} run {run}"


def cancel(act: Act, target: Target, options: Options) -> str:
    """Cancel a run that a newer run of its workflow superseded.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``run`` and ``superseded-by``.

    Returns:
        What was done.
    """
    gate(act, "cancel", target.repo)
    run, newer = option(options, "run"), option(options, "superseded-by")
    act.hub.write(
        Change(kind="cancel", repo=target.repo, fields={"run": run, "newer": newer})
    )
    return f"cancel {target.repo} run {run} (superseded by {newer})"


def dispatch_workflow(act: Act, target: Target, options: Options) -> str:
    """Dispatch relock.yml or check.yml.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``workflow`` and ``ref``.

    Returns:
        What was done.

    Raises:
        Refused: another workflow.
    """
    gate(act, "dispatch-workflow", target.repo)
    workflow, ref = option(options, "workflow"), option(options, "ref")
    if workflow not in WORKFLOWS:
        raise Refused(
            f"{workflow} is not one pitboss dispatches ({', '.join(WORKFLOWS)})"
        )
    act.hub.write(
        Change(
            kind="dispatch", repo=target.repo, fields={"workflow": workflow, "ref": ref}
        )
    )
    return f"dispatch-workflow {workflow} on {target.repo} at {ref}"


def close(act: Act, target: Target, options: Options) -> str:
    """Close an issue or a PR with GitHub's state_reason.

    Args:
        act: the verb's world.
        target: the issue or PR.
        options: ``reason`` (completed, not_planned, duplicate).

    Returns:
        What was done.

    Raises:
        Refused: another reason.
    """
    gate(act, "close", target.repo)
    reason = text(options.get("reason"))
    if reason not in CLOSE_REASONS:
        raise Refused(f"close names GitHub's state_reason: {', '.join(CLOSE_REASONS)}")
    act.hub.write(
        Change(
            kind="close-issue",
            repo=target.repo,
            number=target.number,
            fields={"reason": reason},
        )
    )
    return f"close {target.repo}#{target.number} ({reason})"
