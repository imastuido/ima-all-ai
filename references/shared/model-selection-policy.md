# Model Selection Policy

This policy applies to image, video, and audio equally.

Owning code:

- `scripts/ima_runtime/shared/catalog.py`
- `scripts/ima_runtime/shared/prefs.py`
- `scripts/ima_runtime/shared/rule_resolution.py`

## Rules

1. The live product list is the source of truth.
2. Use exact runtime `model_id`, not friendly marketing names.
3. Use `version_id` when multiple leaves share one `model_id` family and leaf-specific behavior matters.
4. Treat saved preferences as hints, not guaranteed availability.
5. Re-check the runtime list before honoring a remembered model.
6. If the runtime exposes only one unique `model_id` family for a `task_type`, the CLI may auto-select it.
7. If the runtime exposes multiple families, the CLI should surface recommended model ids instead of silently auto-picking one.
8. For Seedance family video tasks, prefer `Seedance 2.0 Fast` ahead of subscription-gated `Seedance 2.0` when no subscription-state signal is available.

## Discovery Commands

```bash
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_image --list-models
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_video --list-models --output-json
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_music --list-models
python3 scripts/ima_create.py --api-key "$IMA_API_KEY" --task-type text_to_speech --list-models --output-json
```

Use `--output-json` when you need rule counts, form fields, or virtual mapping surfaces before selecting a model.

## Leaf Selection

- `model_id` identifies the family
- `version_id` identifies the concrete product leaf
- `attribute_id` and `credit` come from the matched rule inside that leaf

Do not confuse those layers.

## Capability Ownership

- candidate discovery belongs to `shared.catalog`
- capability packages turn selected model data into `ModelBinding`
- payload construction uses the selected leaf plus rule-matched params

## Current Canonical Owner

Model alias normalization and rule-value degradation helpers now live in `scripts/ima_runtime/shared/rule_resolution.py`.
