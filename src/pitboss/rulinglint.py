"""A ruling's steps must pass the gates they lead to (keyword: ruling-lint, bats#654).

bats#654: an Opus ruling ordered a sentence deleted from the ticket, without running
plan-check against its own steps, so the ruling could not be carried out. A ruling
that edits the ticket or the PR body states each edit as a line of its steps::

    1. ticket delete: Found by quire#1118.
    2. body replace: old text => new text

``findings`` applies the edits to copies and runs the gates the PR must then pass:
the Plan holds the ticket's Done-when word for word (``plan-done-when``), each item
is stated as demonstrated (``done-when-form``) and the body keeps the PR body's form
(``lint pr-body``). A step whose text is not there is impossible and is named.
"""

from typing import Sequence

from . import forms, plandigest, plandonewhen, rulingedits

FAILS = "gate {gate}: after the ruling's steps, {finding}"


def findings(ruling: str, ticket: str, body: str, head: str) -> Sequence[str]:
    """What the ruling's steps leave failing.

    Args:
        ruling: the ruling's text.
        ticket: the ruled-on ticket's body.
        body: the PR's body.
        head: the head the body's ``Head:`` line must name.

    Returns:
        A finding for each step whose text is not there, naming the step; when
        every step applies, a finding for each gate the copies then fail, naming
        the gate. Nothing when the ruling orders no edit.
    """
    texts = {"ticket": ticket, "body": body}
    lost = rulingedits.applied(ruling, texts)
    if lost or not rulingedits.orders_edits(ruling):
        return lost
    before = set(_gates(ticket, body, head))  # failures the ruling did not cause
    return [
        each
        for each in _gates(texts["ticket"], texts["body"], head)
        if each not in before
    ]


def _gates(ticket: str, body: str, head: str) -> Sequence[str]:
    plan = plandigest.section(body)
    subject = forms.Subject(name="body", body=body, head=head)
    gates = (
        ("plan-check", plandonewhen.findings(plan, ticket)),
        ("plan-check", plandonewhen.form(ticket)),
        ("lint pr-body", forms.pr_body(subject, [], [])),
    )
    return [
        FAILS.format(gate=gate, finding=finding)
        for gate, found in gates
        for finding in found
    ]
