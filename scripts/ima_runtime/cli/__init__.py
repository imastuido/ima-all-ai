"""Canonical CLI package for the current public runtime."""

from ima_runtime.cli.flow import run_cli
from ima_runtime.cli.parser import build_parser
from ima_runtime.cli.presenter import print_model_summary

__all__ = [
    "build_parser",
    "print_model_summary",
    "run_cli",
]
