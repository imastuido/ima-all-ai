> Legacy redirect: This file is retained for compatibility. Canonical docs now live under `references/gateway/*`, `references/shared/*`, and `capabilities/*`.

# User Scenario Map

Use this file when the request is phrased in user/business language and you need to map it to the correct runtime route.

This is a scenario map, not the full rulebook.

- For exact routing rules and clarification gates, see `routing-and-inputs.md`
- For model family vs leaf rules, see `../models/model-id-and-defaults.md`
- For create payload and rule resolution, see `../models/product-list-and-create-params.md`
- For agent-side messaging and clarification flow, see `workflow-and-ux.md`

## How To Use This Map

1. Find the closest user goal below.
2. Choose one generation step only.
3. If the request mixes multiple media outputs, split into multiple steps.
4. If image roles are unclear, clarify before routing.

## Scenario Table

| User goal | Typical phrasing | Primary route | Must have | Clarify when |
| --- | --- | --- | --- | --- |
| Create a brand-new image | "画一张图", "generate an image", "文生图" | `text_to_image` | prompt | user also provided source images and may actually want editing |
| Edit or transform an existing image | "改这张图", "图生图", "edit this image" | `image_to_image` | prompt + 1+ input images | multiple images are provided and main-vs-reference roles are unclear |
| Generate a text-only video | "做个广告视频", "文生视频", "generate a video" | `text_to_video` | prompt | user also provided images or implied first/last/reference semantics |
| Animate an existing image | "把这张图做成视频", "animate this image" | `image_to_video` | prompt + 1+ input images | more than one image is provided and image roles are unclear |
| Control a video with first and last frames | "第一张首帧，第二张尾帧", "first frame + last frame" | `first_last_frame_to_video` | prompt + exactly 2 input images + explicit first/last semantics | user only provided two images but never described them as first/last |
| Generate a video using reference assets or style | "按这几张图的风格做视频", "reference-style video" | `reference_image_to_video` | prompt + 1+ reference assets (`image`, `video`, or `audio`) + explicit reference semantics | multiple images are present but user never said they are references |
| Generate background music or song | "做段 BGM", "生成音乐", "compose music" | `text_to_music` | prompt | request also needs video timing or sync claims |
| Generate speech / voiceover | "配音", "朗读这段话", "TTS" | `text_to_speech` | text prompt | request also needs timing alignment with video |
| Deliver a multi-asset package | "视频+BGM+配音", "整套素材", "campaign assets" | multi-step workflow | split into separate calls | user expects one automatic call to do image/video/music/tts together |

## Video With Images: Fast Decision Guide

Use this order:

1. explicit first-frame / last-frame semantics -> `first_last_frame_to_video`
2. explicit reference / style semantics -> `reference_image_to_video`
3. explicit "animate this image" semantics -> `image_to_video`
4. no stable image-role semantics -> clarify first

Hard rules:

- Two images does not automatically mean `first_last_frame_to_video`
- Multiple images does not automatically mean `reference_image_to_video`
- If image roles are unclear, do not guess

## Clarify-First Scenarios

You must clarify before routing when:

- the user provides 2 images but does not say whether they are first/last frames
- the user provides multiple images but does not say whether they are references
- the user mixes "animate this" and "reference this style" language
- the user asks for multiple output media in one sentence and expects one call

Recommended question forms:

- "这两张图分别是什么角色？是首帧/尾帧，还是参考风格图，还是只想把其中一张动起来？"
- "这些图里哪一张是主图？其他图片是参考图还是尾帧？"
- "你这次要我先做视频，还是先做音乐 / 配音？这几个输出需要拆成多步。"

## Model Selection Handoff

After the route is stable:

1. run `--list-models` for the chosen `task_type`
2. choose exact `model_id`
3. inspect `version_id` when the same `model_id` appears multiple times
4. then move to create payload / parameter alignment

## Anti-Patterns

- Mapping a user request directly from keywords to `task_type` without checking image roles
- Treating "two photos" as enough evidence for first-frame + last-frame control
- Treating "multiple photos" as enough evidence for reference-video routing
- Selecting a model before the route is stable
- Treating a multi-media package request as one CLI call
