"""The ``review-form`` command: the form a review comment must take."""

import argparse

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    checkruns,
    commandarguments,
    commands,
    config,
    gateform,
    gates,
    ghapi,
    gradeline,
    headchecks,
    reviewci,
)

BODY_NOTE = (
    "# also one line of its own: Body: <digest> (uvx pitboss body-digest FILE, the"
    " PR body saved to a file); the sweep keys a review with no such line to the"
    " head alone"
)


def _gate_source(repo: config.Repo, gate: gates.Gate) -> str:
    where = f"# the form is read from {gates.WORKFLOW} of {repo.slug}"
    if gate.form is not None:
        return f"{where} (its default branch)"
    return (
        f"{where}, which this cannot read: read the file; the configured gated"
        " form follows, and may not be the gate's"
    )


@ENTRY_DATA.register(
    commandarguments.CONFIG_ARGUMENT,
    add_argument("repository"),
    add_argument(
        "--head",
        default=None,
        help="the head SHA to be reviewed: refuse (exit 1, each run and its state"
        " printed) while a CI run of it is not completed and successful",
    ),
    name="review-form",
)
def review_form(args: argparse.Namespace) -> None:
    """Print the form a review comment in a repository must take.

    Args:
        args: the parsed arguments.
    """
    settings = commands.load_settings(args)
    found = gateform.read(args.safe_run, settings, args.repository)
    repo, workflow, review, form = found.repo, found.gate, found.review, found.form
    if args.head:  # case 38 (keyword: review-ci)
        github = ghapi.read_only(args.safe_run)
        runs = checkruns.current_checks(
            headchecks.runs_of(github, repo, args.head), args.head
        )
        refused = reviewci.lines(args.head, runs)
        for line in refused:
            print(line)
        if refused:
            raise SystemExit(1)
    gated = repo.slug in review.gated
    print(f"# {repo.slug}: {'gated' if gated else 'not gated'}")
    if workflow is not None:
        print(_gate_source(repo, workflow))
    print(
        f"# {{sha}}: the full head SHA; {{verdict}}: {form.approved!r} or"
        f" {form.changes_needed!r}"
    )
    if gated:
        trusted = workflow.trusted if workflow else sorted(review.trusted)
        print(f"# {gates.note(trusted)}")
    for line in form.lines:
        print(line)
    print(gradeline.FORM_NOTE)
    print(gradeline.FORM_LINE)
    print(BODY_NOTE)
