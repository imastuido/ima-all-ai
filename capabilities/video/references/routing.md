# Video Routing

Owning code: `scripts/ima_runtime/capabilities/video/routes.py`

## Decision Order

1. explicit `intent_hints.task_type`
2. explicit `intent_hints.video_mode`
3. single-image fallback
4. clarification for 2+ ambiguous images
5. text-only fallback

## Concrete Rules

- `video_mode=first_last_frame` -> `first_last_frame_to_video`
- `video_mode=reference` -> `reference_image_to_video`
- one image and no stronger hint -> `image_to_video`
- two or more images without stable roles -> clarification
- no images -> `text_to_video`

## Why This Exists

The old root routing docs mixed gateway classification with video-specific branching.
This file owns only the video branch now.
