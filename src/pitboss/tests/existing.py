"""Whether a test that a table names exists in ``pitboss.tests``."""

from .. import claims


def resolvable(name: str) -> bool:
    """Whether a test named ``module.Class.method`` or ``module.method`` exists.

    Args:
        name: the name, from ``pitboss.tests``.

    Returns:
        True when it resolves.
    """
    return claims.resolves(str(__package__), name)
