# Gateway Entry And Routing

This is the source of truth for how a request enters the new runtime architecture.

Owning code:

- `scripts/ima_runtime/gateway/router.py`
- `scripts/ima_runtime/gateway/planner.py`
- `scripts/ima_runtime/capabilities/image/routes.py`
- `scripts/ima_runtime/capabilities/video/routes.py`
- `scripts/ima_runtime/capabilities/audio/routes.py`

## Gateway Shell

The gateway receives a `GatewayRequest` and returns one of:

- `RouteDecision` for a single capability
- `WorkflowPlanDraft` for multi-target work
- `ClarificationRequest` when the route is not stable yet

## Media Target Rules

- no target: ask whether the user wants image, video, or audio
- one target: route directly to that capability
- more than one target: build an ordered workflow plan
- invalid targets: stop with clarification instead of silently dropping them

The planner normalizes multi-target requests into `image -> video -> audio`.

## Capability Entry Rules

### Image

- no source image: `text_to_image`
- one or more source images: `image_to_image`

### Video

- explicit `intent_hints.task_type`: trust it if it is a supported video task
- `video_mode=first_last_frame`: `first_last_frame_to_video`
- `video_mode=reference`: `reference_image_to_video`
- exactly one input image with no stronger hint: `image_to_video`
- two or more input images without stable roles: ask for clarification
- no images: `text_to_video`

### Audio

- `audio_mode=music`: `text_to_music`
- `audio_mode=speech`: `text_to_speech`
- otherwise: ask whether the user wants music or speech

## Clarification Boundary

Do not move into model selection or execution if any of these are true:

- the user asked for video with 2+ images but did not explain image roles
- the user asked for audio but did not say music vs speech
- the request includes unsupported or mixed media targets that need correction

## Handoff

After the route is stable:

1. pick the owning capability docs
2. resolve a live `model_id`
3. apply the capability-owned domain rules for routing and params
4. execute one task at a time through the current production path

Current runtime note:

- image, video, and audio execution are all wired through their capability paths
- multi-output workflows now expose a public CLI plan/confirm surface and still execute one capability step at a time
