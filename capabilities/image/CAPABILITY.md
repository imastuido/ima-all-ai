# Image Capability

Owning code:

- `scripts/ima_runtime/capabilities/image/routes.py`
- `scripts/ima_runtime/capabilities/image/models.py`
- `scripts/ima_runtime/capabilities/image/params.py`
- `scripts/ima_runtime/capabilities/image/executor.py`

## Responsibility

The image capability owns the image domain contract for single-step image generation and editing:

- `text_to_image`
- `image_to_image`

Its package defines the routed `TaskSpec`, model-binding, and param-normalization seams for image requests.

## Current Runtime State

- The image capability package is the source of truth for image-domain routing, model, parameter, and execution behavior.
- The public CLI now runs image requests through `execute_image_task()`.

## Read Order

1. `references/scenarios.md`
2. `references/routing.md`
3. `references/models.md`
4. `references/params.md`

## Boundaries

- The gateway decides whether the request is image vs video vs audio.
- Shared policy decides model discovery, failures, and security.
- This capability owns the image-domain contract and the current production CLI execution path for image tasks.
