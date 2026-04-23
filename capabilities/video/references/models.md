# Video Models

Owning code:

- `scripts/ima_runtime/capabilities/video/models.py`
- `scripts/ima_create.py`

## Real CLI Path

The production execution path is still the CLI:

```bash
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_video --list-models
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type image_to_video --model-id <runtime-model-id> --prompt "<prompt>"
```

The capability package mirrors that path in-process:

- discover rows from `shared.catalog`
- build a `ModelBinding`
- execute through `execute_video_task()`

Seedance note:

- `ima-pro` / `ima-pro-fast` media-based video tasks may additionally prepare `src_image`, `src_video`, and `src_audio`
- those prepared media sections are capability-owned, not agent-built

## Binding Rules

Carry these fields through the binding:

- `model_id`
- `model_id_raw`
- `model_version`
- `attribute_id`
- `credit`
- `form_params`
- `rule_attributes`
- `all_credit_rules`
- `virtual_mappings`

## Polling

Video execution uses the task-type-specific poll config from `POLL_CONFIG`, which is longer than the image/audio defaults.
