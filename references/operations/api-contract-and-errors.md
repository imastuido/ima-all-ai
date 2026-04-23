> Legacy redirect: This file is retained for compatibility. Canonical docs now live under `references/gateway/*`, `references/shared/*`, and `capabilities/*`.

# API Contract And Errors

## Core API Sequence

1. Optional local upload flow (`imapi.liveme.com`) when `--input-images`, `--reference-videos`, or `--reference-audios` contain local paths, and when local reference videos need cover-frame upload.
2. Product list (`/open/v1/product/list`) to discover model/version/form fields.
3. Optional Seedance asset verify (`/open/v1/assets/verify`) for compliance-gated media-based video runs.
4. Create task (`/open/v1/tasks/create`).
5. Poll task detail (`/open/v1/tasks/detail`) until terminal status.

## Responsibility Split

- Local validation catches JSON-shape issues, unsupported extra params, and some input-count mistakes before create-task.
- `create_task_with_reflection` handles create-time retries for selected backend errors.
- Poll-time failures/timeouts are diagnosed after task creation; they are not automatically recreated as new tasks today.
- For the detailed mapping from product-list leaf fields to create payload fields, see `../models/product-list-and-create-params.md`.

## Error Code Source Of Truth

Business error handling must use the API response body `code`.

Rules:

1. If the backend response body includes `code`, use that as the runtime error code.
2. Do not treat HTTP transport status such as `500` or `401` as the business error code by itself.
3. If an HTTP error has no API `code` in the response body, classify it as transport/unknown rather than inventing a business code from `http_status`.
4. Retry decisions should be based on API `code`, not on HTTP status text or status number alone.

This matters because transport failures and business-rule failures are different classes of problems.
Mixing them makes retries noisy and can misdiagnose DNS/network issues as model or parameter issues.

## Task Types

- `text_to_image`
- `image_to_image`
- `text_to_video`
- `image_to_video`
- `first_last_frame_to_video`
- `reference_image_to_video`
- `text_to_music`
- `text_to_speech`

## Error Matrix

| Phase | Signal | Meaning | First action | Next action |
| --- | --- | --- | --- | --- |
| local validation | input count / JSON error | request shape is invalid before API create | fix route, input count, or `--extra-params` JSON | retry |
| local validation | virtual UI value cannot be mapped | user supplied a UI-facing value that has no valid `value_mapping` target | show valid UI-facing options and ask user to correct input | retry after clarification |
| pre-create | model not found | requested `model_id` is absent in current runtime list | rerun `--list-models` | pick exact runtime `model_id` |
| create | `401` / unauthorized | key invalid | rotate key | retry once |
| create | `4008` | insufficient credits | top up / lower-cost model | retry |
| create | `500` | backend rejects complexity or transient failure | degrade params using runtime rules | switch model if repeated |
| create | `6009` | no matching rule | add missing rule attributes | retry |
| create | `6010` | attribute mismatch | reselect credit rule by params | retry |
| create/poll | minimum pixel error | requested size is below model minimum | increase size | retry |
| poll | timeout | task not ready in max wait | reduce complexity | check dashboard / creation record |
| poll | failed/deleted status | task reached terminal failure after creation | inspect dashboard context | retry manually or switch model |

## Interface / Parameter / Upload Triage

Apply in this order before retrying:

1. Interface check: task_type matches intent + media inputs.
2. Parameter check: remove unsupported keys and normalize values.
   For virtual UI fields, normalize UI value -> backend field/value before rule matching.
3. Upload check: local paths vs URLs classified correctly.
4. Model check: model exists in current runtime list.

## Retry Policy (Current Implementation)

Create-time automatic reflection currently behaves like this:

- attempt 1: keep prompt, sanitize params
- attempt 2: apply rule-based degradation or rule reconciliation
- attempt 3: one final reduced profile
- after max attempts: stop and return contextual diagnosis

Auto-retry triggers implemented today:

- `500`
- `6009`
- `6010`

These triggers are keyed off the extracted API `code`.
An HTTP `500` without an API body `code=500` is not treated as the same thing.

Not automatically recreated today:

- `401`
- `4008`
- model-not-found preflight failures
- poll-time timeout / failed / deleted statuses

## Expected Failure Output Shape

Final error to user should include:

- attempt summary (`x/y`)
- likely cause (plain language)
- 1-3 concrete next actions
- reference code (if available)
- model/task context when it helps narrow the issue

For invalid virtual UI values:

- show only valid UI-facing choices
- do not present backend enum values as the user's corrective options
