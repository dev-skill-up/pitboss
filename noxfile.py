"""Sessions."""

import nox


@nox.session(python=["3.12", "3.13"])
def tests(session):
    """Run the tests with coverage, failing under 100 percent."""
    session.install("-e", ".[tests]")
    session.run("coverage", "run", "--branch", "-m", "unittest", "discover", "-s", "src/pitboss/tests", "-t", "src")
    session.run("coverage", "report", "--fail-under=100", "--include=src/pitboss/*", "--omit=*/tests/*")
