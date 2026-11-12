"""Run one existing test from another test (keyword: mutation-check).

A rule's register row names the tests that guard its function. When the mutation
check finds a mutant that those tests do not kill but a test of another module does,
the row gets a test of its own that runs that test, so the row's guard is stated
where the register reads it.
"""

import importlib


def rerun(test: str) -> None:
    """Run a test, raising what it raises.

    Args:
        test: ``module.Class.method`` of a module of ``pitboss.tests``.
    """
    module_name, class_name, method = test.rsplit(".", 2)
    case = getattr(importlib.import_module(f"pitboss.tests.{module_name}"), class_name)
    case(method).debug()
