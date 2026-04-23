---
name: "IMA All-in-One AI Creator"
version: 1.4.6
category: file-generation
author: IMA Studio (imastudio.com)
keywords: imastudio, ai creation, multimodal, all-in-one, image generator, video generator, music generator, TTS, seedream, midjourney, nano banana, wan, kling, veo, sora, suno, doubao, seed-tts, AI绘画, AI视频, AI音乐, 语音合成
argument-hint: "[text prompt, image URL, or music/speech description]"
description: >
  Gateway skill for IMA's multimodal creator. Route requests into image, video, audio,
  or workflow capability docs. The public CLI now supports single-task execution plus
  confirmed multi-output workflow plan/run flows with exact runtime model_id resolution.
requires:
  runtime:
    - python3
    - ffmpeg
    - ffprobe
  packages:
    - requests
    - keyring
  primaryCredential: IMA_API_KEY
  credentialNote: "IMA_API_KEY is required for API calls, but not before installation. The runtime prefers IMA_API_KEY from the environment, stores bootstrap credentials in the system keyring, and keeps only keyring metadata in ~/.openclaw/memory/ima_bootstrap.json."
metadata:
  openclaw:
    primaryEnv: IMA_API_KEY
    homepage: https://www.imaclaw.ai
    requires:
      bins:
        - python3
persistence:
  readWrite:
    - ~/.openclaw/memory/ima_bootstrap.json
    - ~/.openclaw/memory/ima_prefs.json
    - ~/.openclaw/memory/ima_workflows/
    - ~/.openclaw/logs/ima_skills/
---

# IMA Studio (All-in-One)

This file is the public gateway. It tells you how to enter the system and where the deeper rules live.

## When To Use

Use this skill when the user wants any of:

- image generation or editing
- video generation from text or images
- music generation or speech / TTS
- a multi-step plan that combines image, video, and/or audio through confirmed sequential runs

## Gateway Contract

1. Detect the target media first: `image`, `video`, `audio`, or a multi-step workflow.
2. Route single-target requests into the matching capability shell.
3. Build a workflow plan when the user wants more than one media output.
4. Clarify instead of guessing when video image roles are ambiguous or when audio intent does not say music vs speech.
5. Resolve the exact runtime `model_id` from the live product list before execution.
6. Keep capability-specific routing, models, and parameters in `capabilities/*`.
7. Keep shared policies for model selection, errors, and security in `references/shared/*`.
8. Make clear whether the CLI is doing a single task or a confirmed sequential workflow; do not present workflow execution as one backend batch task.

## Public Runtime Surface

- The public CLI is `python3 scripts/ima_create.py`.
- Environment bootstrap is available via `python3 scripts/ima_create.py --bootstrap`.
- Beginner mode accepts a positional prompt and defaults to image generation.
- Single-task mode uses `--task-type`.
- Seedance `reference_image_to_video` also accepts `--reference-videos` and `--reference-audios`.
- Workflow planning uses `--media-targets` and should usually save a reviewed plan via `--plan-file`.
- Workflow confirmation uses `--plan-file` + `--confirm-plan-hash` + `--confirm-workflow`.
- Workflow inventory is available via `--list-workflows`.
- Error-code quick reference lives at [`references/shared/error-code-action-guide.md`](references/shared/error-code-action-guide.md).
- `plan_hash` represents the reviewed confirmable workflow object, not just the step skeleton.
- Workflow resume uses `--resume-from-step` plus `--reuse-output step_id=url` for skipped upstream steps.
- Workflow capability docs define planning, confirmation, and sequential execution rules for multi-output requests.

## Read Order

1. `references/gateway/entry-and-routing.md`
2. `references/gateway/workflow-confirmation.md`
3. `references/shared/model-selection-policy.md`
4. `references/shared/error-policy.md`
5. `references/shared/error-code-action-guide.md`
6. `references/shared/security-and-network.md`
7. `capabilities/image/CAPABILITY.md`
8. `capabilities/video/CAPABILITY.md`
9. `capabilities/audio/CAPABILITY.md`
10. `capabilities/workflow/CAPABILITY.md`

## Boundary

- Do not treat this file as the full rulebook.
- Do not bypass capability docs when route/model/param detail matters.
- Do not trust stale model tables over the live runtime.
- Only `ima-pro` / `ima-pro-fast` require mandatory compliance verification for media-based Seedance video tasks.
