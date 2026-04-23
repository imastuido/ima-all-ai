# Image Scenarios

## Supported Outcomes

| User need | Task type | Required inputs |
| --- | --- | --- |
| create a new image | `text_to_image` | prompt |
| edit / transform an existing image | `image_to_image` | prompt + `input_images` |

## Typical Requests

- "做一张主视觉海报" -> `text_to_image`
- "把这张图修成电影灯光" -> `image_to_image`
- "保留构图，换成秋季配色" -> `image_to_image`

## Non-Goals

- no multi-step audio/video orchestration
- no automatic video routing from image prompts alone
- no hidden model selection without live discovery
