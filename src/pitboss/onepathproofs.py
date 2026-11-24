"""Every proof of the one path with its seed, by the modules that hold them.

``CASES`` is each bullet's proof and the one edit that breaks it (``proofseeds``,
one-path). The proofs are in ``answerproofs``, ``actproofs``, ``pureproofs``,
``readproofs``, ``retryproofs`` and ``rulingproofs``, and P4's in ``modeproof``.
"""

from typing import Mapping

from . import (
    actproofs,
    answerproofs,
    gateproofs,
    pureproofs,
    readproofs,
    retryproofs,
    rulingproofs,
)
from .proofcase import Case

CASES: Mapping[str, Case] = {
    **answerproofs.CASES,
    **actproofs.CASES,
    **gateproofs.CASES,
    **pureproofs.CASES,
    **readproofs.CASES,
    **retryproofs.CASES,
    **rulingproofs.CASES,
}
