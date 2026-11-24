"""Every proof of the one path with its seed, by the modules that hold them.

``CASES`` is each bullet's proof and the one edit that breaks it (``proofseeds``,
one-path). The proofs are in ``answerproofs``, ``actproofs``, ``pureproofs``,
``readproofs``, ``retryproofs`` and ``rulingproofs``, and P4's in ``modeproof``.
"""

from typing import Mapping

from . import (
    actproofs,
    answerproofs,
    doneproofs,
    gateproofs,
    progressproofs,
    pureproofs,
    readproofs,
    repoproofs,
    retryproofs,
    rulingproofs,
)
from .proofcase import Case

CASES: Mapping[str, Case] = {
    **answerproofs.CASES,
    **actproofs.CASES,
    **doneproofs.CASES,
    **gateproofs.CASES,
    **progressproofs.CASES,
    **pureproofs.CASES,
    **readproofs.CASES,
    **repoproofs.CASES,
    **retryproofs.CASES,
    **rulingproofs.CASES,
}
