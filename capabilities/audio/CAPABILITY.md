# Audio Capability

Owning code:

- `scripts/ima_runtime/capabilities/audio/routes.py`
- `scripts/ima_runtime/capabilities/audio/models.py`
- `scripts/ima_runtime/capabilities/audio/params.py`
- `scripts/ima_runtime/capabilities/audio/executor.py`

## Responsibility

The audio capability owns the audio domain contract for both:

- `text_to_music`
- `text_to_speech`

Its package defines the audio routing, model-binding, and param-normalization seams for music and speech requests.

## Current Runtime State

- The audio capability package is the source of truth for audio-domain routing, model, parameter, and execution behavior.
- The public CLI now runs audio requests through `execute_audio_task()`.

## Read Order

1. `references/scenarios.md`
2. `references/routing.md`
3. `references/models.md`
4. `references/params.md`

## Boundary

Audio does not promise sync with video by itself. Workflow coordination handles ordered multi-output plans, and external validation is required before claiming exact timing alignment.
