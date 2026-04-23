"""Compatibility shim for the legacy `ima_runtime.cli_flow` import path."""

from __future__ import annotations

import sys

from ima_runtime.cli import flow as _canonical_flow

sys.modules[__name__] = _canonical_flow
