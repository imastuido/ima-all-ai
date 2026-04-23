> Legacy redirect: This file is retained for compatibility. Canonical docs now live under `references/gateway/*`, `references/shared/*`, and `capabilities/*`.

# Routing And Inputs

## Primary Objective

Make task routing deterministic, especially under weaker base models.

## Responsibility Split

- Agent layer: classify user intent, choose `task_type`, map natural-language constraints into canonical params, and pick the exact `model_id`.
- CLI layer: validate input counts, sanitize `--extra-params`, upload local media, create/poll the task, and print warnings/errors.
- Do not assume `ima_create.py` can infer the correct route or model directly from raw prose alone.

## Media-Type First (Hard Rule)

Always classify user intent before model selection.

| User intent keywords | Media type | task_type candidates |
| --- | --- | --- |
| image, picture, 画图, 生成图 | image | `text_to_image`, `image_to_image` |
| video, 视频, 动画, 图生视频 | video | `text_to_video`, `image_to_video`, `first_last_frame_to_video`, `reference_image_to_video` |
| music, song, BGM, 音乐 | music | `text_to_music` |
| speech, TTS, 配音, 朗读 | speech | `text_to_speech` |

If user asks for multiple media outputs in one request, split into ordered workflow steps instead of a single mixed call.

## Interface Recognition Matrix

| User request signal | Final task_type | Must have |
| --- | --- | --- |
| only text prompt + image intent | `text_to_image` | prompt |
| image modification + source image | `image_to_image` | prompt + 1+ input images |
| only text prompt + video intent | `text_to_video` | prompt |
| animate static image | `image_to_video` | prompt + 1+ input images |
| first+last frame phrasing | `first_last_frame_to_video` | prompt + exactly 2 input images |
| reference style phrasing | `reference_image_to_video` | prompt + 1+ reference assets (`image`, `video`, or `audio`) |
| bgm/song intent | `text_to_music` | prompt |
| voiceover/tts intent | `text_to_speech` | text prompt |

## Input Role Semantics

Do not infer image role from image count alone.

The router must identify what each provided image means in the user's request:

- source image to animate or modify
- first frame
- last frame
- reference/style image
- unknown role

Hard rules:

1. Two images does not automatically mean `first_last_frame_to_video`.
2. Multiple images does not automatically mean `reference_image_to_video`.
3. Image count is secondary evidence. User-described role semantics win.
4. If the model cannot reliably determine the image role from context, it must clarify with the user before routing.

## Two-Image Routing Rules

When the user provides 2 images for a video request:

| Context | Final task_type |
| --- | --- |
| explicit first-frame / last-frame semantics | `first_last_frame_to_video` |
| explicit reference / style semantics | `reference_image_to_video` |
| explicit "animate this image" semantics centered on one main image | `image_to_video` |
| only "two images" but no reliable role semantics | clarify first |

Examples:

- "第一张是首帧，第二张是尾帧" -> `first_last_frame_to_video`
- "用这两张图当参考风格生成视频" -> `reference_image_to_video`
- "把第一张图做成视频，第二张只是参考风格" -> `reference_image_to_video`
- "给你两张图，做个视频" -> clarify first

## Clarification Gate

The router must stop and ask the user when the available context is insufficient to choose between:

- `image_to_video`
- `first_last_frame_to_video`
- `reference_image_to_video`

Clarification is required when any of these are true:

1. 2 or more images are provided but their roles are not explicitly described.
2. The wording could reasonably map to more than one video route.
3. The request mentions both motion intent and reference intent without a clear primary route.

Recommended clarification question shape:

- "这两张图分别是什么角色？是首帧/尾帧，还是参考风格图，还是只想把其中一张动起来？"

## Ambiguity Resolution Priority

When one request matches multiple routes, decide in this order:

1. explicit user constraint ("first frame + last frame", "reference")
2. media-input evidence (has image inputs or not)
3. default route by media type
4. if route is still ambiguous, clarify before routing

Examples:

- "把这张图做成视频" + has image -> `image_to_video`
- "做个参考风格视频" + has reference images -> `reference_image_to_video`
- "做 10 秒广告视频" + no image -> `text_to_video`
- "给你两张图做视频" + no role semantics -> clarify first
- "第一张是首帧，第二张是尾帧，做个 10 秒视频" -> `first_last_frame_to_video`
- "这两张图是参考风格，做个 10 秒广告视频" -> `reference_image_to_video`

## Parameter Normalization Map

Normalize phrasing into canonical keys before sending `--extra-params`:

- "时长", "seconds", "duration" -> `duration`
- "分辨率", "1080p", "720p" -> `resolution`
- "尺寸", "size", "1:1", "9:16" -> `size` or `aspect_ratio` (model dependent)
- "女声/男声", "voice" -> `voice_id` or `voice_type`
- "语速", "speed" -> `speed`
- "音调", "pitch" -> `pitch`
- "音量", "volume" -> `volume`

Rules:

1. Only send keys supported by runtime model config (`form_config` + `credit_rules`).
2. Unknown keys are dropped with warning summary.
3. `--extra-params` must be a JSON object.
4. Some user-visible values belong to virtual UI fields and may need mapping to a different backend field before create.
5. If both a UI virtual field and its backend field are present, backend field wins.
6. If a UI virtual value cannot be mapped, stop and clarify with the user instead of guessing.

Important caveat:

- Do not assume every user-facing choice such as `720p` or `1080p` maps directly to backend `resolution`.
- For `is_ui_virtual=true` fields, the UI-facing field may differ from the real create payload field.
- Example pattern: user-facing `quality=1080p` may need to resolve to backend `mode=pro`.

When this applies, use the product-leaf `value_mapping` semantics from `../models/product-list-and-create-params.md` before treating the parameter as final.

Recommended clarification style for invalid virtual UI values:

- explain that the current user-facing option is unsupported for this model
- show only valid UI-facing choices
- do not expose backend enum values as if they were user choices

## Current CLI Controls

- `--model-id` must be an exact runtime `model_id`.
- `--version-id` optionally pins a specific runtime version leaf.
- `--input-images` can be repeated; all groups are flattened before validation.
- `--size` is a convenience shortcut merged into `--extra-params`.
- Unsupported extra params are dropped before create-task with a warning.

## OSS Upload Recognition Rules

Input is local file if:

- starts with `/`
- starts with `./` or `../`
- starts with `file://`

Input is remote URL if:

- starts with `http://` or `https://`

Runtime behavior:

- local image/video inputs: runtime uploads to OSS/CDN and then creates task
- remote URL inputs: runtime uses URL directly
- text-only task types ignore input images

## Validation Boundaries

- The CLI enforces count-based requirements for `image_to_image`, `image_to_video`, `reference_image_to_video`, and `first_last_frame_to_video`.
- `first_last_frame_to_video` requires exactly 2 inputs.
- `reference_image_to_video` accepts either 1+ input images or 1+ reference media assets (`--reference-videos` / `--reference-audios`).
- Text-only task types (`text_to_image`, `text_to_video`, `text_to_music`, `text_to_speech`) ignore `--input-images` with a warning.
- The CLI does not understand semantic roles beyond the chosen `task_type`; if the route is wrong, validation can only partially recover it.
- Therefore, role ambiguity must be resolved before the CLI call, not after it.

## Anti-Patterns (Must Avoid)

- Passing `--input-images` to text-only task types (`text_to_image`, `text_to_video`, `text_to_music`, `text_to_speech`).
- Choosing `image_to_video` when no image input exists.
- Treating "two images" as sufficient evidence for `first_last_frame_to_video`.
- Treating "multiple images" as sufficient evidence for `reference_image_to_video`.
- Auto-routing ambiguous multi-image requests without clarification.
- Inferring `model_id` from friendly name without product list check.
- Sending arbitrary extra params without model compatibility check.

## Minimal Decision Flow

1. Identify media type.
2. Determine image roles from user context, not image count alone.
3. Resolve task_type.
4. If task_type is still ambiguous, clarify with the user before proceeding.
5. Validate input-image count for selected task_type.
6. Query runtime models (`--list-models`) when uncertain.
7. Pick exact `model_id`.
8. Normalize parameters and remove unsupported fields.
9. Verify local-vs-URL input handling.
10. Execute generation command.
