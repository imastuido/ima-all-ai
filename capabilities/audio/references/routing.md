# Audio Routing

Owning code: `scripts/ima_runtime/capabilities/audio/routes.py`

## Rule

Audio routing depends on `intent_hints.audio_mode`:

- `music` -> `text_to_music`
- `speech` -> `text_to_speech`
- missing or unknown -> `ClarificationRequest`

The gateway should already have decided that the target capability is audio.
