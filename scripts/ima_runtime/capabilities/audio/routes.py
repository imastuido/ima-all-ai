from __future__ import annotations

from ima_runtime.shared.types import ClarificationRequest, GatewayRequest, TaskSpec


def build_audio_task_spec(request: GatewayRequest) -> TaskSpec | ClarificationRequest:
    mode = request.intent_hints.get("audio_mode")
    if mode == "music":
        return TaskSpec(
            capability="audio",
            task_type="text_to_music",
            prompt=request.prompt,
            extra_params=request.extra_params,
        )
    if mode == "speech":
        return TaskSpec(
            capability="audio",
            task_type="text_to_speech",
            prompt=request.prompt,
            extra_params=request.extra_params,
        )
    return ClarificationRequest(
        reason="audio output kind missing",
        question="这次要生成音乐还是配音？",
        options=("音乐", "配音"),
    )
