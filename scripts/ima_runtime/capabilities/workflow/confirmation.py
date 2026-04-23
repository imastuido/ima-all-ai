from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ima_runtime.capabilities.workflow.plan_types import ConfirmablePlan
from ima_runtime.shared.types import GatewayRequest, MediaSource, WorkflowExecutionResult, WorkflowPlanDraft, WorkflowStepDraft


_WORKFLOW_CAPABILITY_ORDER = {
    "image": 0,
    "video": 1,
    "audio": 2,
}


def _validate_workflow_structure(plan: WorkflowPlanDraft) -> None:
    if not plan.steps:
        raise ValueError("Confirmable workflow plan must contain at least one step.")

    highest_rank = -1
    for step in plan.steps:
        current_rank = _WORKFLOW_CAPABILITY_ORDER.get(step.capability)
        if current_rank is None:
            raise ValueError(f"Unsupported workflow capability: {step.capability}")
        if current_rank < highest_rank:
            raise ValueError("Workflow steps must follow image -> video -> audio ordering.")
        highest_rank = current_rank


def _validate_workflow_step_ids(plan: WorkflowPlanDraft) -> None:
    seen_step_ids: set[str] = set()
    for step in plan.steps:
        if step.step_id in seen_step_ids:
            raise ValueError(f"Duplicate workflow step_id: {step.step_id}")
        seen_step_ids.add(step.step_id)


def _validate_workflow_dependencies(plan: WorkflowPlanDraft) -> None:
    prior_step_ids: set[str] = set()
    for step in plan.steps:
        for dependency in step.depends_on:
            if dependency not in prior_step_ids:
                raise ValueError(
                    f"Workflow step '{step.step_id}' references unknown dependency '{dependency}'."
                )
        prior_step_ids.add(step.step_id)


def to_confirmable_plan(plan: WorkflowPlanDraft) -> ConfirmablePlan:
    _validate_workflow_structure(plan)
    _validate_workflow_step_ids(plan)
    _validate_workflow_dependencies(plan)
    return plan


def request_to_dict(request: GatewayRequest) -> dict[str, Any]:
    return {
        "prompt": request.prompt,
        "media_targets": list(request.media_targets),
        "input_images": list(request.input_images),
        "reference_media": [
            {
                "kind": item.kind,
                "source": item.source,
                "role": item.role,
            }
            for item in request.reference_media
        ],
        "intent_hints": dict(request.intent_hints),
        "extra_params": dict(request.extra_params),
    }


def request_from_dict(payload: Mapping[str, Any]) -> GatewayRequest:
    return GatewayRequest(
        prompt=str(payload.get("prompt") or ""),
        media_targets=tuple(payload.get("media_targets") or ()),
        input_images=tuple(payload.get("input_images") or ()),
        reference_media=tuple(
            MediaSource(
                kind=str(item.get("kind") or ""),
                source=str(item.get("source") or ""),
                role=str(item.get("role") or "reference"),
            )
            for item in (payload.get("reference_media") or [])
            if item.get("kind") and item.get("source")
        ),
        intent_hints=dict(payload.get("intent_hints") or {}),
        extra_params=dict(payload.get("extra_params") or {}),
    )


def plan_from_payload(payload: Mapping[str, Any]) -> WorkflowPlanDraft:
    return WorkflowPlanDraft(
        summary=str(payload.get("summary") or ""),
        steps=tuple(
            WorkflowStepDraft(
                step_id=str(step.get("step_id") or ""),
                capability=str(step.get("capability") or ""),
                goal=str(step.get("goal") or ""),
                depends_on=tuple(step.get("depends_on") or ()),
            )
            for step in (payload.get("steps") or [])
        ),
    )


def _confirmable_plan_identity(plan_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "request": dict(plan_payload.get("request") or {}),
        "summary": plan_payload.get("summary"),
        "steps": list(plan_payload.get("steps") or []),
        "confirmation_required": bool(plan_payload.get("confirmation_required", True)),
        "can_execute_now": bool(plan_payload.get("can_execute_now", False)),
        "missing_requirements": list(plan_payload.get("missing_requirements") or []),
        "model_requirements": dict(plan_payload.get("model_requirements") or {}),
        "credit_preview": dict(plan_payload.get("credit_preview") or {}),
    }


def compute_confirmable_plan_hash(plan_payload: Mapping[str, Any]) -> str:
    canonical_identity = _confirmable_plan_identity(plan_payload)
    return hashlib.sha256(
        json.dumps(canonical_identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def build_confirmable_plan_payload(
    *,
    plan: WorkflowPlanDraft,
    request: GatewayRequest,
    steps_payload: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    model_requirements: Mapping[str, Any],
    missing_requirements: list[str],
    credit_preview: Mapping[str, Any],
    suggested_commands: list[str],
) -> dict[str, Any]:
    provisional_payload = {
        "request": request_to_dict(request),
        "summary": plan.summary,
        "confirmation_required": True,
        "can_execute_now": not missing_requirements,
        "missing_requirements": list(missing_requirements),
        "model_requirements": dict(model_requirements),
        "credit_preview": dict(credit_preview),
        "steps": list(steps_payload),
    }
    plan_hash = compute_confirmable_plan_hash(provisional_payload)
    return {
        "mode": "workflow_plan",
        "plan_id": f"wf-{plan_hash[:12]}",
        "plan_hash": plan_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": plan.summary,
        "confirmation_required": True,
        "can_execute_now": not missing_requirements,
        "missing_requirements": list(missing_requirements),
        "model_requirements": dict(model_requirements),
        "suggested_commands": list(suggested_commands),
        "credit_preview": dict(credit_preview),
        "request": request_to_dict(request),
        "steps": list(steps_payload),
    }


def _workflow_store_dir(store_dir: str | Path | None = None) -> Path:
    if store_dir is not None:
        return Path(store_dir).expanduser()
    return Path(
        os.getenv("IMA_WORKFLOW_STORE_DIR")
        or os.path.expanduser("~/.openclaw/memory/ima_workflows")
    )


def _default_artifact_path(plan_id: str, store_dir: str | Path | None = None) -> Path:
    return _workflow_store_dir(store_dir) / f"{plan_id}.json"


def _write_json_file(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def persist_confirmable_plan(
    payload: Mapping[str, Any],
    plan_file: str | None,
    store_dir: str | Path | None = None,
) -> tuple[dict[str, Any], Path]:
    plan_payload = dict(payload)
    artifact_path = _default_artifact_path(str(plan_payload["plan_id"]), store_dir)
    plan_payload["artifact_path"] = str(artifact_path)
    plan_payload.setdefault("execution_history", [])

    _write_json_file(artifact_path, plan_payload)

    if plan_file:
        plan_path = Path(plan_file).expanduser()
        if plan_path.resolve() != artifact_path.resolve():
            _write_json_file(plan_path, plan_payload)

    return plan_payload, artifact_path


def load_plan_payload(plan_file: str) -> dict[str, Any]:
    path = Path(plan_file).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Workflow plan file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid workflow plan JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Workflow plan file must contain a JSON object: {path}")
    return payload


def _format_tampered_plan_error(*, expected_plan_hash: str, embedded_plan_hash: str) -> str:
    return (
        "工作流计划已被修改，无法执行。\n\n"
        "原因：计划文件内容与生成时记录的确认码不一致，说明计划在生成后发生了变动。\n\n"
        "解决方案：\n"
        "1. 重新运行规划命令，生成新的计划文件。\n"
        "2. 或恢复原始计划文件后，再次执行确认命令。\n\n"
        f"详情：当前 plan_hash={expected_plan_hash}，文件内 plan_hash={embedded_plan_hash}。"
    )


def _format_confirm_hash_mismatch(*, expected_plan_hash: str, provided_plan_hash: str) -> str:
    return (
        "工作流计划确认码不匹配。\n\n"
        "原因：你传入的 `--confirm-plan-hash` 与计划文件当前内容不一致。\n\n"
        "解决方案：\n"
        "1. 打开计划文件，使用其中最新的 `plan_hash` 重新执行。\n"
        "2. 如果计划已经修改过，请先重新规划，再确认执行。\n\n"
        f"详情：当前 plan_hash={expected_plan_hash}，传入值={provided_plan_hash}。"
    )


def load_reviewed_plan(plan_file: str, confirm_plan_hash: str) -> dict[str, Any]:
    plan_payload = load_plan_payload(plan_file)
    if plan_payload.get("mode") != "workflow_plan":
        raise RuntimeError("--plan-file must contain a workflow plan payload.")

    expected_plan_hash = compute_confirmable_plan_hash(plan_payload)
    embedded_plan_hash = str(plan_payload.get("plan_hash") or "")
    if embedded_plan_hash != expected_plan_hash:
        raise RuntimeError(
            _format_tampered_plan_error(
                expected_plan_hash=expected_plan_hash,
                embedded_plan_hash=embedded_plan_hash,
            )
        )
    if expected_plan_hash != confirm_plan_hash:
        raise RuntimeError(
            _format_confirm_hash_mismatch(
                expected_plan_hash=expected_plan_hash,
                provided_plan_hash=confirm_plan_hash,
            )
        )
    to_confirmable_plan(plan_from_payload(plan_payload))
    return plan_payload


def list_saved_workflows(store_dir: str | Path | None = None) -> list[dict[str, Any]]:
    workflow_dir = _workflow_store_dir(store_dir)
    if not workflow_dir.exists():
        return []

    workflows: list[dict[str, Any]] = []
    for path in workflow_dir.glob("*.json"):
        try:
            payload = load_plan_payload(str(path))
        except RuntimeError:
            continue
        if payload.get("mode") != "workflow_plan":
            continue

        steps = list(payload.get("steps") or [])
        total_steps = len(steps)
        history = list(payload.get("execution_history") or [])
        latest_history = history[-1] if history else {}
        completed_steps = len(latest_history.get("steps") or [])
        if total_steps and completed_steps >= total_steps and history:
            status = "completed"
        elif completed_steps:
            status = "partial"
        else:
            status = "planned"

        workflows.append(
            {
                "plan_id": str(payload.get("plan_id") or path.stem),
                "plan_hash": str(payload.get("plan_hash") or ""),
                "summary": str(payload.get("summary") or ""),
                "status": status,
                "progress": f"{min(completed_steps, total_steps)}/{total_steps}",
                "step_count": total_steps,
                "completed_steps": min(completed_steps, total_steps),
                "created_at": str(payload.get("created_at") or ""),
                "last_activity_at": str(latest_history.get("executed_at") or ""),
                "artifact_path": str(path.expanduser()),
            }
        )

    workflows.sort(
        key=lambda item: (
            item.get("last_activity_at") or item.get("created_at") or "",
            item.get("plan_id") or "",
        ),
        reverse=True,
    )
    return workflows


def append_execution_history(
    plan_payload: Mapping[str, Any],
    workflow_result: WorkflowExecutionResult,
    *,
    resume_from_step: str | None,
    plan_file: str | None,
    store_dir: str | Path | None = None,
) -> Path:
    artifact_path = Path(
        plan_payload.get("artifact_path")
        or _default_artifact_path(str(plan_payload.get("plan_id") or "workflow"), store_dir)
    ).expanduser()

    current_payload = dict(plan_payload)
    if artifact_path.exists():
        current_payload = load_plan_payload(str(artifact_path))

    history = list(current_payload.get("execution_history") or [])
    history.append(
        {
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "resume_from_step": resume_from_step,
            "steps": [
                {
                    "step_id": step.step_id,
                    "capability": step.capability,
                    "task_type": step.task_type,
                    "task_id": step.task_id,
                    "url": step.url,
                    "cover_url": step.cover_url,
                    "model_id": step.model_id,
                    "model_name": step.model_name,
                    "depends_on": list(step.depends_on),
                }
                for step in workflow_result.steps
            ],
        }
    )
    current_payload["artifact_path"] = str(artifact_path)
    current_payload["execution_history"] = history

    _write_json_file(artifact_path, current_payload)

    if plan_file:
        plan_path = Path(plan_file).expanduser()
        if plan_path.resolve() == artifact_path.resolve():
            _write_json_file(plan_path, current_payload)

    return artifact_path


__all__ = [
    "append_execution_history",
    "build_confirmable_plan_payload",
    "compute_confirmable_plan_hash",
    "list_saved_workflows",
    "load_plan_payload",
    "load_reviewed_plan",
    "persist_confirmable_plan",
    "plan_from_payload",
    "request_from_dict",
    "request_to_dict",
    "to_confirmable_plan",
]
