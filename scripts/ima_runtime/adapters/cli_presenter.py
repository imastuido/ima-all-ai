"""Compatibility shim for the legacy `ima_runtime.adapters.cli_presenter` path."""

from __future__ import annotations

import sys

from ima_runtime.cli import presenter as _canonical_presenter

sys.modules[__name__] = _canonical_presenter
