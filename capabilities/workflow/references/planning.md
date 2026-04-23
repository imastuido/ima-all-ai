# Workflow Planning

Owning code:

- `scripts/ima_runtime/gateway/planner.py`
- `scripts/ima_runtime/capabilities/workflow/coordinator.py`
- `scripts/ima_runtime/capabilities/workflow/executor.py`

## Planner Output

The planner returns either:

- `ClarificationRequest`
- `WorkflowPlanDraft`

A plan contains:

- a summary
- ordered `WorkflowStepDraft` items
- stable `step_id` values
- dependency links

## Ordering Rule

Supported targets are normalized into:

1. image
2. video
3. audio

That ordering is independent of how the user listed them.
