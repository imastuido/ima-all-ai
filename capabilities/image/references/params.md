# Image Parameters

Owning code: `scripts/ima_runtime/capabilities/image/params.py`

## Allowed Shared Keys

The image capability keeps only supported keys from:

- model `form_params`
- matched rule attributes
- virtual UI mappings
- image-safe shared keys such as `size`, `resolution`, `quality`, `aspect_ratio`, `mode`

Unknown keys are dropped.

## Virtual UI Fields

When a model exposes a UI-facing virtual field:

- map the UI value through `virtual_mappings`
- send the backend target field/value pair
- if both UI field and backend field are present, the backend field wins
- if the UI value cannot be mapped, raise `VirtualParamMappingError`

## Execution Handoff

Within the capability package, `execute_image_task()` sanitizes params, calls `create_task_with_reflection()`, then polls until one usable image URL is available.

Current runtime note:

- this is the package-level execution seam for image
- the public CLI now relies on this executor path for image requests
