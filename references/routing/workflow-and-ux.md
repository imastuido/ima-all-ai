> Legacy redirect: This file is retained for compatibility. Canonical docs now live under `references/gateway/*`, `references/shared/*`, and `capabilities/*`.

# Workflow And UX

## Responsibility Split

- `ima_create.py` executes one `task_type` per invocation.
- Multi-media requests are orchestrated at the agent/workflow layer, not by a single mixed runtime call.
- UX templates below describe the agent wrapper experience, not raw CLI stdout.
- If routing is ambiguous, the agent/workflow layer must clarify before calling the CLI.

## Standard Single-Task Workflow

1. Acknowledge intent and key constraints.
2. Determine media type and candidate `task_type`.
3. If route is still ambiguous, clarify image roles or route intent with the user.
4. Resolve model and sanitize parameters.
5. Execute generation.
6. Poll until completion or timeout.
7. Return result URL + compact metadata.

## Clarification Before Execution

Do not present a route as final if the request could still map to more than one video interface.

Typical clarification-required cases:

- 2 or more images are provided, but their roles are not explicit
- the request could mean `image_to_video`, `first_last_frame_to_video`, or `reference_image_to_video`
- the user mixes "animate this" language with "reference style" language

Recommended clarification prompts:

- "这两张图分别是什么角色？是首帧/尾帧，还是参考风格图，还是只想把其中一张动起来？"
- "这几张图是要做首尾帧控制，还是作为参考风格图？"

Do not continue to model selection or generation until the route is stable.

## Agent-Orchestrated Multi-Media Workflow (Not Automatic)

For requests like "promo video + BGM + voiceover":

1. Build visual anchor first (image or script-driven video).
2. Generate video and capture final duration.
3. Generate music in a separate call using a matching target duration.
4. Generate TTS/voiceover in another separate call and verify timing fit externally.
5. Report whether sync is exact/approximate/unchecked.

Each numbered step above is a separate generation call. The current CLI does not chain these automatically.

## UX Message Templates

### Initial Acknowledge

Chinese example:

- "已识别为 `text_to_video`，将先查询可用模型并按你的时长与分辨率约束执行。"

### Clarification Needed

Chinese examples:

- "当前还不能稳定判断该走 `image_to_video`、`first_last_frame_to_video` 还是 `reference_image_to_video`，我先确认一下这几张图的角色。"
- "这两张图里，哪一张是主图？是否需要把第一张当首帧、第二张当尾帧？"

### In-Progress

- "任务已创建，正在轮询状态（约 30-120 秒，取决于模型）。"

### Success

- "生成完成：URL=...，model_id=...，task_id=...，主要参数=..."

### Failure

- "本次失败原因：...；建议下一步：1) ... 2) ..."

## Output Contracts

### CLI `--output-json` (Current)

Successful JSON output currently includes:

- `task_id`
- `url`
- `cover_url`
- `model_id`
- `model_name`
- `credit`

### Agent Response (Recommended)

When wrapping the CLI for end users, include:

- `url`
- `task_id`
- `model_id`
- user-visible parameters you actually passed from invocation context (duration/resolution/voice where applicable)

Do not claim the backend returned or verified extra metadata unless it was explicitly captured.

## Duration Discipline

When media are combined:

- Video duration is the anchor.
- Music/TTS should be fit-checked against video duration.
- The current CLI does not compute sync fidelity for you.
- Do not claim synchronized output unless fit-check was completed.

## UX Anti-Patterns

- Claiming the final `task_type` before route ambiguity is resolved.
- Treating two images as sufficient evidence for first-frame + last-frame routing.
- Treating multiple images as sufficient evidence for reference-image routing.
- Reporting success without URL.
- Hiding model_id/task_id when debugging context is needed.
- Claiming a multi-media pipeline ran in one automatic call.
- Claiming precise sync when no timing check occurred.
