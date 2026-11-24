"""The readers that make typed values from GitHub's JSON (keyword: any-expr, #524).

Each is held to ``--disallow-any-expr`` with the decision's closure
(``pyproject.toml``), so nothing untyped reaches the decision: a field of another
shape reads as empty (``totaljson``), not as whatever ``json.loads`` gave.
``tests/test_any_expr`` computes the modules that make a value of a type the
decision consumes (``tests/anyfeeders``, from the annotations under
``world.World``) and the modules that parse a response into a ``shapes`` record,
fails when one is not listed, and fails on a line that is neither.
"""

READERS = frozenset(
    {
        "pitboss.actread",
        "pitboss.blockedby",
        "pitboss.earlyreview",
        "pitboss.examine",
        "pitboss.failures",
        "pitboss.handbackderive",
        "pitboss.ledger",
        "pitboss.pinsonly",
        "pitboss.planapproved",
        "pitboss.pullobject",
        "pitboss.pullstate",
        "pitboss.queue",
        "pitboss.readworld",
        "pitboss.stuckci",
        "pitboss.workorder",
        "pitboss.gateread",
        "pitboss.ghstore",
        "pitboss.headchecks",
        "pitboss.issuelist",
        "pitboss.parsing",
        "pitboss.pulls",
    }
)
