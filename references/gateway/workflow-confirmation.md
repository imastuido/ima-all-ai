# Workflow Confirmation

Owning code:

- `scripts/ima_runtime/capabilities/workflow/coordinator.py`
- `scripts/ima_runtime/capabilities/workflow/confirmation.py`
- `scripts/ima_runtime/gateway/planner.py`

## What The Workflow Shell Does

The workflow shell is for multi-target requests only. It does not execute media generation itself.

Current behavior:

1. normalize the requested media targets
2. build an ordered `WorkflowPlanDraft`
3. adapt that draft into a confirmable plan

Today `to_confirmable_plan()` is an identity adapter. It is still a deliberate seam: confirmation policy lives there, not in the gateway router.

Current ownership note:

- the gateway/router decides whether a workflow exists at all
- `capabilities/workflow/confirmation.py` owns the reviewed plan object, `plan_hash`, artifact persistence, and confirmation-time validation
- CLI flow should only orchestrate those confirmation APIs, not redefine them

Current public surface note:

- the public CLI exposes workflow planning via `--media-targets`
- reviewed workflow plans should be persisted with `--plan-file`
- confirmed workflow execution uses `--plan-file` + `--confirm-plan-hash` + `--confirm-workflow`
- optional per-capability runtime models can be supplied with `--workflow-models`
- resume flow uses `--resume-from-step` and `--reuse-output`
- workflow plans now expose next-step guidance such as `missing_requirements`, `suggested_commands`, and `credit_preview`
- `plan_hash` must match the full reviewed confirmable object, including model requirements and credit preview
- confirm-run must not override reviewed model bindings; re-plan instead
- each confirmed workflow step still becomes its own media-generation call

## Persistence Contract

Planning writes a reviewed payload to a canonical artifact:

- default store dir: `~/.openclaw/memory/ima_workflows/`
- override with `IMA_WORKFLOW_STORE_DIR`
- default artifact path: `<store_dir>/<plan_id>.json`

If `--plan-file` points somewhere else, planning writes the same reviewed payload to both places:

- canonical artifact at `artifact_path`
- caller-selected review file at `--plan-file`

Execution history rules:

- `execution_history` is appended after each confirmed run or resume
- the canonical write target is always `artifact_path`
- `--plan-file` is only updated in-place when it resolves to the same path as `artifact_path`
- copied review files are not the canonical history store

Confirm-run state rules:

- request state is reloaded from the reviewed plan payload, not from live CLI prompt/input flags
- confirm-run must refuse CLI-side overrides that mutate reviewed request or model state
- resume metadata belongs in `execution_history`, not in the immutable plan identity

## Step Ordering

Current order is fixed:

1. `image`
2. `video`
3. `audio`

This keeps downstream assets dependent on upstream outputs. Video can depend on image, and audio can depend on either earlier step when the workflow owner decides to fit timing later.

## Confirmation Contract

Before executing a workflow:

- show the ordered steps
- show which steps depend on earlier outputs
- make clear that each step becomes a separate generation call
- do not promise exact sync unless a later validation step verifies it

## Clarification Contract

Return a `ClarificationRequest` instead of a plan when:

- there is no supported media target
- a target is unsupported
- the route inside one capability is still ambiguous
