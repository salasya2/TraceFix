from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from tracefix.agent.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from tracefix.agent.providers import ModelProvider, ProviderResult
from tracefix.agent.router import ToolRouter
from tracefix.domain.contracts import Diagnosis, EvidenceRef


OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a source file from the authorized snapshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "snapshot_id": {"type": "string"},
                    "relative_path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["snapshot_id", "relative_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search authorized source paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "snapshot_id": {"type": "string"},
                    "query": {"type": "string"},
                    "allowed_paths": {"type": "array", "items": {"type": "string"}},
                    "result_limit": {"type": "integer"},
                },
                "required": ["snapshot_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_diff",
            "description": "Return the original failing run diff if present.",
            "parameters": {
                "type": "object",
                "properties": {"snapshot_id": {"type": "string"}},
                "required": ["snapshot_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_patch",
            "description": "Submit a unified diff for validation and verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "snapshot_id": {"type": "string"},
                    "unified_diff": {"type": "string"},
                },
                "required": ["snapshot_id", "unified_diff"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_test",
            "description": "Request an approved test profile on the exploration sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string"},
                    "approved_profile_id": {"type": "string"},
                    "permitted_test_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["candidate_id", "approved_profile_id"],
            },
        },
    },
]


@dataclass
class AgentOutcome:
    patch: str | None
    diagnosis: Diagnosis | None
    calls: list[ProviderResult]
    input_tokens: int
    output_tokens: int
    simulated: bool
    prompt_version: str = PROMPT_VERSION


async def run_agent(
    provider: ModelProvider,
    router: ToolRouter,
    *,
    tenant_id: str,
    run_id: str,
    traceback: str,
    snapshot_id: str,
    execution_sha: str,
    tests: str,
    model: str,
    max_turns: int = 6,
) -> AgentOutcome:
    user = build_user_prompt(
        traceback=traceback, snapshot_id=snapshot_id, execution_sha=execution_sha, tests=tests
    )
    calls: list[ProviderResult] = []
    in_tok = 0
    out_tok = 0
    diagnosis: Diagnosis | None = None
    for _ in range(max_turns):
        result = await provider.complete(system=SYSTEM_PROMPT, user=user, tools=OPENAI_TOOLS, model=model)
        calls.append(result)
        in_tok += result.input_tokens
        out_tok += result.output_tokens
        if result.tool_calls:
            observations: list[str] = []
            for call in result.tool_calls:
                try:
                    output = router.call(
                        call["name"], call.get("arguments") or {}, tenant_id=tenant_id, run_id=run_id
                    )
                except Exception as exc:  # tool errors are evidence, not privileges
                    output = f"tool error: {exc}"
                observations.append(f"{call['name']}: {output}")
            user = "Tool results:\n" + "\n".join(observations)
            continue
        diagnosis = _parse_diagnosis(result.text, execution_sha)
        break
    return AgentOutcome(
        patch=router.submitted_patch,
        diagnosis=diagnosis,
        calls=calls,
        input_tokens=in_tok,
        output_tokens=out_tok,
        simulated=any(c.simulated for c in calls) or getattr(provider, "simulated", False),
    )


def _parse_diagnosis(text: str, revision: str) -> Diagnosis | None:
    blob = _extract_json(text)
    if not blob:
        return None
    evidence = []
    for item in blob.get("evidence") or []:
        evidence.append(
            EvidenceRef(
                path=item.get("path", ""),
                revision=item.get("revision", revision),
                start_line=item.get("start_line"),
                end_line=item.get("end_line"),
            )
        )
    return Diagnosis(
        failure_category=str(blob.get("failure_category", "unknown")),
        hypothesis=str(blob.get("hypothesis", "")),
        expected_behavior=str(blob.get("expected_behavior", "")),
        known_limitations=list(blob.get("known_limitations") or []),
        evidence=evidence,
        proposed_changed_paths=list(blob.get("proposed_changed_paths") or []),
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return None
