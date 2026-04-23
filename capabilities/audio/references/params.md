# Audio Parameters

Owning code: `scripts/ima_runtime/capabilities/audio/params.py`

## Allowed Keys

The audio capability keeps shared audio keys such as:

- `voice_id`
- `voice_type`
- `speed`
- `pitch`
- `volume`
- `lyrics`
- `genre`
- `mood`
- `duration`
- `tone`
- `style`

Unknown keys are dropped.

## Virtual Mapping

Audio models can expose UI-facing fields such as `tone` that map to backend fields like `style`.

Rules:

- resolve UI values through `virtual_mappings`
- backend field wins on conflict
- invalid UI values raise `VirtualParamMappingError`

## Execution Notes

- audio execution uses task-type-specific poll config
- the executor falls back across `url`, `preview_url`, and `watermark_url`
- no `input_images` are part of the normal audio create path

Current runtime note:

- these are the package-level audio execution rules
- the public CLI now depends on the audio executor for audio requests
