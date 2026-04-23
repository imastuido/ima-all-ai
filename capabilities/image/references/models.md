# Image Models

Owning code: `scripts/ima_runtime/capabilities/image/models.py`

## Candidate Discovery

Image candidates come from `shared.catalog.list_all_models(product_tree, task_type=spec.task_type)`.

The capability projects those rows into `ModelCandidate` values and later into a `ModelBinding`.

## Expectations

- choose an image-capable `model_id`
- use the exact `version_id` returned by discovery when leaf pinning matters
- carry `form_params`, `rule_attributes`, `all_credit_rules`, and `virtual_mappings` forward into execution

## Common Families

Examples seen in current docs and tests:

- `gpt-image-2`
- `gemini-3.1-flash-image`
- `gemini-3-pro-image`
- `doubao-seedream-4.5`

Treat these as examples, not a static registry.
