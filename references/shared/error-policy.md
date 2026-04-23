# Error Policy

This policy applies across the gateway, shared runtime, and all execution capabilities.

Owning code:

- `scripts/ima_runtime/shared/errors.py`
- `scripts/ima_runtime/shared/retry_logic.py`
- `scripts/ima_runtime/shared/task_execution.py`

## Source Of Truth

Use the API response body `code` as the business error code.

Do not promote raw HTTP status into a business code when the body does not include one.

## Retry Policy

Automatic create-time reflection is limited to:

- `500`
- `6009`
- `6010`

Current strategies:

- `500`: degrade parameter complexity
- `6009`: add missing rule attributes
- `6010`: reselect the credit rule for the current params

## Non-Retry Cases

- invalid or unauthorized key
- insufficient credits
- model not found in live discovery
- poll-time failed / deleted terminal status
- transport errors without an API business code

## Timeout Policy

Timeouts are diagnosed, not auto-recreated as new tasks.

- video timeouts point the user to the creation-record URL
- non-video timeouts point the user to the dashboard

## Failure Output Contract

The final user-facing error should include:

- attempts used
- likely cause
- concrete next actions
- reference code when available
- model/task context

## Common Code Actions

See:

- `error-code-action-guide.md`

Especially important user-action mappings:

- `401` -> regenerate or obtain API key at `https://www.imaclaw.ai/imaclaw/apikey`
- `4008` -> top up / upgrade at `https://www.imaclaw.ai/imaclaw/subscription`
- `4014` -> subscription upgrade required at `https://www.imaclaw.ai/imaclaw/subscription`
- `6009` / `6010` -> rule mismatch; remove overrides or use a compatible profile
- `500` -> simplify parameters and retry

## Current Canonical Owners

- `scripts/ima_runtime/shared/errors.py` owns failure parsing, diagnosis, and user-facing failure formatting.
- `scripts/ima_runtime/shared/retry_logic.py` owns create-time retry/reflection behavior.
- `scripts/ima_runtime/shared/task_execution.py` owns task create/poll execution.
