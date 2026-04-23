# Video Capability

Owning code:

- `scripts/ima_runtime/capabilities/video/routes.py`
- `scripts/ima_runtime/capabilities/video/models.py`
- `scripts/ima_runtime/capabilities/video/params.py`
- `scripts/ima_runtime/capabilities/video/executor.py`
- `scripts/ima_runtime/capabilities/video/reference_media.py`
- `scripts/ima_runtime/capabilities/video/compliance.py`

## Responsibility

The video capability owns every single-step video interface:

- `text_to_video`
- `image_to_video`
- `first_last_frame_to_video`
- `reference_image_to_video`

It is the capability with the highest clarification burden because image-role ambiguity changes the interface.

For Seedance (`ima-pro`, `ima-pro-fast`) only, the capability also owns:

- multimodal reference media preparation for `reference_image_to_video`
- strict preflight validation for Seedance media-based task types
- mandatory compliance verification before create-task

## Read Order

1. `references/scenarios.md`
2. `references/routing.md`
3. `references/models.md`
4. `references/params.md`

## Boundaries

- the gateway decides whether the request is video at all
- the video capability decides which video interface to use
- workflow orchestration for multi-output packages lives in the workflow capability
