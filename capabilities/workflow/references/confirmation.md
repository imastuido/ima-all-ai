# Workflow Confirmation

Owning code: `scripts/ima_runtime/capabilities/workflow/confirmation.py`

## Current Behavior

`to_confirmable_plan()` currently returns the incoming draft unchanged.

That is still a real boundary:

- confirmation policy belongs here
- reviewed plan payload construction, hashing, persistence, and load-time validation now also live here
- gateway routing should not absorb that responsibility

## Operator Rule

Before running a multi-output plan, confirm:

- step order
- dependency chain
- whether later steps depend on earlier generated assets
- whether timing fit is verified or still unchecked

Public CLI surface:

- `--media-targets ...` prints the plan
- `--plan-file` persists the reviewed plan object
- `--confirm-plan-hash` verifies the reviewed plan identity
- `--confirm-workflow` executes the confirmed plan step by step
- `--workflow-models` can pin per-capability runtime `model_id` values
- `--resume-from-step` plus `--reuse-output` lets operators continue a failed workflow without regenerating completed upstream steps
- workflow plan output also includes `missing_requirements`, `suggested_commands`, and `credit_preview` when enough runtime information is available

Hash rule:

- `plan_hash` must represent the reviewed confirmable plan object, not only the workflow skeleton
- changing model requirements, missing requirements, or credit preview changes the hash
- confirm-run must refuse CLI-side model overrides that would mutate the reviewed plan

Persistence rule:

- planning always writes a canonical artifact under the workflow store directory
- `artifact_path` is the canonical history file for later execution updates
- if `--plan-file` is a different review path, it is a copy of the reviewed payload, not the canonical history sink
- confirmed runs append `execution_history` to `artifact_path`
