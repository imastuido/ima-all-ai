# Video Parameters

Owning code: `scripts/ima_runtime/capabilities/video/params.py`

## Allowed Keys

Video sanitization accepts supported keys from:

- `form_params`
- matched rule attributes
- virtual UI mappings
- video-safe shared keys such as `duration`, `resolution`, `quality`, `aspect_ratio`, `sound`, `mode`

Unknown keys are dropped before execution.

## Virtual Mapping

Video models commonly expose UI values such as `quality=1080p` that map to backend fields like `mode=pro`.

Rules:

- resolve UI values through `virtual_mappings`
- backend field wins if both UI field and backend field are present
- invalid UI values raise `VirtualParamMappingError`

Seedance note:

- production Seedance leaves currently expose `audio`, `duration`, `resolution`, and `aspect_ratio`
- on the Seedance path, `generate_audio` is normalized into canonical `audio`
- reference video/audio inputs are not form params; they travel through top-level `src_video` / `src_audio`

## Rule Matching

Payload construction may change `attribute_id` and `credit` after params are normalized. That is expected; do not freeze those values too early.
