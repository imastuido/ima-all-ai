# Scripts Runtime Layout

This directory contains the Python runtime behind the public command:

- `scripts/ima_create.py`

## Live Execution Path

The current production execution path is:

1. `scripts/ima_create.py`
2. `ima_runtime/cli/`
3. `ima_runtime/cli/flow.py`
4. `ima_runtime/capabilities/`
5. `ima_runtime/shared/`

The legacy modules `ima_runtime/cli_flow.py`, `ima_runtime/cli_parser.py`, and
`ima_runtime/adapters/cli_presenter.py` now exist as compatibility shims that
alias to the canonical CLI package.

That is the path to read first when you want to understand what the CLI does today.

## Canonical CLI Package

- `ima_runtime/cli/__init__.py`
  Canonical CLI package exports for `run_cli`, `build_parser`, and `print_model_summary`.
- `ima_runtime/cli/flow.py`
  Main CLI orchestration path. It validates arguments, builds runtime requests, calls capability modules, and formats CLI output.
- `ima_runtime/cli/parser.py`
  CLI flag definitions only.
- `ima_runtime/cli/presenter.py`
  CLI output helpers such as model summary rendering.

## Legacy Compatibility Surfaces

- `ima_runtime/cli_flow.py`
  compatibility shim for older imports; aliases to `ima_runtime.cli.flow`
- `ima_runtime/cli_parser.py`
  compatibility shim for older imports; aliases to `ima_runtime.cli.parser`
- `ima_runtime/adapters/cli_presenter.py`
  compatibility shim for older imports; aliases to `ima_runtime.cli.presenter`

## Directory Map

- `scripts/ima_create.py`
  Thin public entrypoint. It wires logging, parser creation, and dependency injection, then hands off to the runtime package.
- `ima_runtime/bootstrap.py`
  Standard-library bootstrap path for dependency installation and local API key persistence before the full runtime imports.
- `scripts/ima_logger.py`
  Local logging setup shared by the CLI entrypoint.
- `ima_runtime/cli/`
  Canonical CLI package for parser, orchestration flow, and presenter helpers.
- `ima_runtime/capabilities/`
  Domain modules for `image`, `video`, `audio`, and `workflow`. This is where routing-by-capability, model binding, param normalization, and execution live.
- `ima_runtime/shared/`
  Cross-capability helpers such as API clients, shared request types, retry logic, preferences, task creation, and task polling.
- `ima_runtime/adapters/`
  Output shaping helpers for the CLI surface. Today this is a very small package.
- `ima_runtime/gateway/`
  Planning and routing seam for normalized requests. Useful for architecture and tests, but not the main CLI execution path today.
- `ima_runtime/contracts.py`
  compatibility layer that re-exports shared runtime types and holds a few higher-level contract dataclasses for tooling and tests.

## Read Order

If you are debugging the real CLI:

1. `scripts/ima_create.py`
2. `ima_runtime/cli/flow.py`
3. the relevant capability package under `ima_runtime/capabilities/`
4. `ima_runtime/shared/`

If you are reasoning about request classification or workflow planning seams:

1. `ima_runtime/gateway/router.py`
2. `ima_runtime/gateway/planner.py`
3. `ima_runtime/capabilities/workflow/`

## Common Misreads

- `ima_runtime/gateway/` is not the primary execution loop for the public CLI.
- `ima_runtime/cli_flow.py` and `ima_runtime/cli_parser.py` are legacy compatibility shims.
- `ima_runtime/contracts.py` is not the source of truth for core runtime types.
  The core request/result dataclasses live in `ima_runtime/shared/types.py`.
- `ima_runtime/capabilities/` is the clearest place to understand domain behavior.
