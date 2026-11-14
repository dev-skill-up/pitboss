"""The verbs that change a PR's state or the project's holds (keyword: act-verbs).

merge, arm and undraft (``gated_write``) run the verdict in the same call as the
write; arm records the head it armed; hold disarms and dequeues the PRs it covers; label
``paused-owner`` and block disarm the PR; override lifts one stop line at one
head, never a failed check or status, a hold, a block, a closed PR or a failed
read.
"""

from . import actcore, totalanswer
from .actcore import disarm_first, head_now, options_of, pull_of, repo_write
from .totaljson import text

LABELS = totalanswer.KNOWN_LABELS | {"p0", "p1", "p2", "p3", actcore.HOLD_LABEL}
WORKFLOWS = ("relock.yml", "check.yml")
CLOSE_REASONS = ("completed", "not_planned", "duplicate")


def gated_write(
    action: str, act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> str:
    """Merge, arm or undraft a PR; arm records its head.

    ``actverbs.run`` applies it only when the item's decision is that verb
    (keyword: gate, P8).

    Args:
        action: ``merge``, ``arm`` or ``undraft``.
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    pull = pull_of(act, target)
    if action == "arm":
        actcore.record(act, target, f"arm head={actcore.head_of(pull)}")
    actcore.put(act, target, action)
    return f"{action} {target.name} at {actcore.head_of(pull)}"


def disarm(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Disarm auto-merge.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    actcore.put(act, target, "disarm")
    return f"disarm {target.name}"


def override_stop(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> str:
    """Lift one stop line for the PR's head, with a reason.

    ``actverbs.run`` applies it only when the line is the stop the item's decision
    answers and an override lifts (a hold, a red, a read GitHub answered with an
    error, a block or a closed PR is never lifted).

    Args:
        act: the verb's world.
        target: the PR.
        options: ``stop`` (the line) and ``reason`` (the ruling it rests on).

    Returns:
        What was done.
    """
    stop, reason = options_of(options, "stop", "reason")
    head = head_now(act, target)
    actcore.record(act, target, f'override head={head} stop="{stop}" reason="{reason}"')
    return f"override {target.name} at {head}"


def block(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Write that a PR waits on another item as a ``Blocked-by:`` line of its body.

    The body is what the one read reads, so ``next`` and ``act`` see the same
    block (keyword: one-path, P8; blocked-by).

    Args:
        act: the verb's world.
        target: the PR.
        options: ``on`` (``owner/name#N``).

    Returns:
        What was done.
    """
    on = actcore.option(options, "on")
    disarm_first(act, target, f"blocked by {on}")
    body = text(pull_of(act, target).get("body")).rstrip("\n")
    actcore.put(act, target, "pr-edit", {"body": f"{body}\nBlocked-by: {on}\n"})
    return f"block {target.name} on {on}"


def label(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Add or remove a label pitboss applies; ``paused-owner`` disarms.

    Args:
        act: the verb's world.
        target: the PR or issue.
        options: ``name``, and ``remove`` to remove it.

    Returns:
        What was done.

    Raises:
        actcore.Refused: a label pitboss does not apply.
    """
    name = actcore.option(options, "name")
    if name not in LABELS:
        raise actcore.Refused(f"label {name} is not one pitboss applies")
    removing = bool(options.get("remove"))
    if name == totalanswer.PAUSED and not removing:
        disarm_first(act, target, totalanswer.PAUSED)
    kind = "unlabel" if removing else "label"
    actcore.put(act, target, kind, {"name": name})
    return f"{kind} {name} on {target.name}"


def hold(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Hold a scope in one repository or all; disarm and dequeue the PRs it covers.

    Args:
        act: the verb's world.
        target: the repository ("all" for every one of the project).
        options: ``scope`` (pushes, merges, undrafts, ci, dispatch, all) and
            ``source`` (the owner message it comes from).

    Returns:
        What was done.
    """
    return actcore.make_hold(act, target.repo, *options_of(options, "scope", "source"))


def unhold(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """End a hold (close its issue).

    Args:
        act: the verb's world.
        target: the hold's issue.
        options: none.

    Returns:
        What was done.
    """
    actcore.put(act, target, "close-issue", {"reason": "completed"})
    return f"unhold {target.name}"


def update_branch(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> str:
    """Merge the base into a PR's branch on GitHub.

    Args:
        act: the verb's world.
        target: the PR.
        options: none.

    Returns:
        What was done.
    """
    disarm_first(act, target, "the branch is updated")
    actcore.put(act, target, "update-branch")
    return f"update-branch {target.name}"


def rerun(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Re-run a run's failed jobs, only for a cause of kind runner.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``run``, ``cause`` (``runner``) and ``evidence`` (the annotation).

    Returns:
        What was done.

    Raises:
        actcore.Refused: the cause is not the runner; a red of the code is fixed by
            a push.
    """
    run = actcore.option(options, "run")
    if options.get("cause") != "runner" or not options.get("evidence"):
        raise actcore.Refused(
            "a re-run needs a cause of kind runner with its evidence (the job's"
            " annotation)"
        )
    repo_write(act, target.repo, "rerun", {"run": run})
    return f"rerun {target.repo} run {run}"


def cancel(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Cancel a run that a newer run of its workflow superseded.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``run`` and ``superseded-by``.

    Returns:
        What was done.
    """
    run, newer = options_of(options, "run", "superseded-by")
    repo = target.repo
    repo_write(act, repo, "cancel", {"run": run, "newer": newer})
    return f"cancel {target.repo} run {run} (superseded by {newer})"


def dispatch_workflow(
    act: actcore.Act, target: actcore.Target, options: actcore.Options
) -> str:
    """Dispatch relock.yml or check.yml.

    Args:
        act: the verb's world.
        target: the repository.
        options: ``workflow`` and ``ref``.

    Returns:
        What was done.

    Raises:
        actcore.Refused: another workflow.
    """
    workflow, ref = options_of(options, "workflow", "ref")
    if workflow not in WORKFLOWS:
        raise actcore.Refused(
            f"{workflow} is not one pitboss dispatches ({', '.join(WORKFLOWS)})"
        )
    repo = target.repo
    repo_write(act, repo, "dispatch", {"workflow": workflow, "ref": ref})
    return f"dispatch-workflow {workflow} on {target.repo} at {ref}"


def close(act: actcore.Act, target: actcore.Target, options: actcore.Options) -> str:
    """Close an issue or a PR with GitHub's state_reason.

    Args:
        act: the verb's world.
        target: the issue or PR.
        options: ``reason`` (completed, not_planned, duplicate).

    Returns:
        What was done.

    Raises:
        actcore.Refused: another reason.
    """
    reason = text(options.get("reason"))
    if reason not in CLOSE_REASONS:
        known = ", ".join(CLOSE_REASONS)
        raise actcore.Refused(f"close names GitHub's state_reason: {known}")
    fields = {"reason": reason}
    change = actcore.Change(
        kind="close-issue", repo=target.repo, number=target.number, fields=fields
    )
    act.hub.write(change)
    return f"close {target.name} ({reason})"
