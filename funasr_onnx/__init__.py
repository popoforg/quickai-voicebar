"""Local compatibility shim for the third-party ``funasr_onnx`` package.

The upstream package imports ``sensevoice_bin`` at package import time, which
pulls in ``torch`` even when the app only uses the ONNX Paraformer and
punctuation models. We extend the package search path to the installed package
location, but avoid importing heavyweight optional modules here.
"""

from __future__ import annotations

import os
import sys


_LOCAL_DIR = os.path.dirname(__file__)

# Allow submodules such as ``funasr_onnx.paraformer_bin`` to resolve from the
# installed wheel without executing the upstream package's heavy __init__.py.
for _entry in list(sys.path):
    if not _entry:
        _entry = os.getcwd()
    _candidate = os.path.join(_entry, "funasr_onnx")
    if os.path.isdir(_candidate) and os.path.realpath(_candidate) != os.path.realpath(_LOCAL_DIR):
        if _candidate not in __path__:
            __path__.append(_candidate)

