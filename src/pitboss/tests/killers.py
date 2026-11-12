"""Run one existing test from another test (keyword: mutation-check).

A rule's register row names the tests that guard its function. When the mutation
check finds a mutant that those tests do not kill but a test of another module does,
the row gets a test of its own that runs that test, so the row's guard is stated
where the register reads it.
"""

import importlib
import unittest
from typing import cast


def rerun(module_name: str, class_name: str, method: str) -> None:
    """Run a test, raising what it raises.

    Args:
        module_name: ``pitboss.tests.module``.
        class_name: the test case's class.
        method: the test's name.
    """
    case = getattr(importlib.import_module(module_name), class_name)
    cast(unittest.TestCase, case(method)).debug()
