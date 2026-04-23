# Image Routing

Owning code: `scripts/ima_runtime/capabilities/image/routes.py`

## Rule

`build_image_task_spec()` is intentionally simple:

- if `GatewayRequest.input_images` is empty, use `text_to_image`
- if any source image is present, use `image_to_image`

The gateway must already have decided that the request belongs to the image capability before this function runs.

## Implication

If the user actually wants animated output, the gateway should route to video instead of trying to repair that mistake here.
