# Workflow Capability

Owning code:

- `scripts/ima_runtime/capabilities/workflow/coordinator.py`
- `scripts/ima_runtime/capabilities/workflow/confirmation.py`
- `scripts/ima_runtime/capabilities/workflow/executor.py`
- `scripts/ima_runtime/gateway/planner.py`

## Responsibility

The workflow capability owns multi-target planning, confirmation, and sequential orchestration.

It turns a multi-output `GatewayRequest` into an ordered, confirmable plan with explicit dependencies between steps, then runs confirmed steps one capability at a time.

In the current runtime, `scripts/ima_runtime/capabilities/workflow/confirmation.py` is the canonical owner for:

- reviewed plan payload construction
- `plan_hash`
- plan artifact persistence
- confirmation-time plan validation

## Read Order

1. `references/planning.md`
2. `references/dependency-rules.md`
3. `references/confirmation.md`

## Boundary

- workflow orchestration does not replace capability executors
- capability executors still run one task at a time
- this shell exists so the gateway can stay thin while confirmed multi-output runs remain explicit
