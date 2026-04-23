# Workflow Dependency Rules

## Current Rule

Each workflow step depends on the immediately previous step.

Examples:

- first step: no dependencies
- second step: depends on the first step id
- third step: depends on the second step id

## Why

The current workflow shell is intentionally conservative:

- image assets can feed video
- video completion can anchor downstream audio decisions
- dependency chains stay easy to confirm and reason about

If the planner becomes more expressive later, this file should change with it.
