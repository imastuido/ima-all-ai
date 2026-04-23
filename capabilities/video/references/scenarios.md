# Video Scenarios

## Supported Outcomes

| User need | Task type | Required inputs |
| --- | --- | --- |
| generate a video from text | `text_to_video` | prompt |
| animate one image | `image_to_video` | prompt + 1 image |
| use first and last frame | `first_last_frame_to_video` | prompt + 2 images with explicit roles |
| use reference images / style | `reference_image_to_video` | prompt + 1+ reference images |

## Clarify-First Cases

- 2 images with no stated roles
- multiple images where it is unclear whether they are references or start/end frames
- mixed "animate this" and "use these as references" language

Those cases should return a `ClarificationRequest`, not a guessed task type.
