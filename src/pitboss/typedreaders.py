"""The readers that make typed values from GitHub's JSON (keyword: any-expr, #524).

Each is held to ``--disallow-any-expr`` with the decision's closure
(``pyproject.toml``), so nothing untyped crosses from a response into a record
of the Observation: a field of another shape reads as empty (``totaljson``), not
as whatever ``json.loads`` gave. ``tests/test_any_expr`` keeps this list the
modules that parse a response and make a ``shapes`` record, and each line live.
"""

READERS = frozenset(
    {
        "pitboss.gateinputs",
        "pitboss.gateread",
        "pitboss.ghstore",
        "pitboss.headchecks",
        "pitboss.issuelist",
        "pitboss.parsing",
        "pitboss.pullparse",
        "pitboss.pulls",
        "pitboss.ticketof",
    }
)
