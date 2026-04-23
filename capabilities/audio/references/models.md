# Audio Models

Owning code: `scripts/ima_runtime/capabilities/audio/models.py`

## Candidate Discovery

Audio candidate discovery uses the same shared product-list flow as image and video, but the selected leaves should be compatible with either:

- music generation
- speech / TTS generation

## Binding Requirements

Carry the same binding metadata used elsewhere:

- `model_id`
- `model_id_raw`
- `model_version`
- `attribute_id`
- `credit`
- `form_params`
- `rule_attributes`
- `all_credit_rules`
- `virtual_mappings`

## Examples

Names and IDs in current tests include examples such as `tts-pro` and `suno`. Treat them as current examples, not a frozen catalog.
