"""Compatibility shim for the legacy `ima_runtime.cli_parser` import path."""

from __future__ import annotations

import sys

from ima_runtime.cli import parser as _canonical_parser

sys.modules[__name__] = _canonical_parser
