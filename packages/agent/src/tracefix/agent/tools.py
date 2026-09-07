from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReadFileArgs(BaseModel):
    snapshot_id: str
    relative_path: str
    start_line: int = 1
    end_line: int = 200


class SearchCodeArgs(BaseModel):
    snapshot_id: str
    query: str
    allowed_paths: list[str] = Field(default_factory=list)
    result_limit: int = 20


class GetDiffArgs(BaseModel):
    snapshot_id: str


class SubmitPatchArgs(BaseModel):
    snapshot_id: str
    unified_diff: str


class RequestTestArgs(BaseModel):
    candidate_id: str
    approved_profile_id: str
    permitted_test_ids: list[str] = Field(default_factory=list)


TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "read_file": ReadFileArgs,
    "search_code": SearchCodeArgs,
    "get_diff": GetDiffArgs,
    "submit_patch": SubmitPatchArgs,
    "request_test": RequestTestArgs,
}


def parse_tool_call(name: str, arguments: dict[str, Any]) -> BaseModel:
    if name not in TOOL_SCHEMAS:
        raise ValueError(f"unknown tool {name}")
    return TOOL_SCHEMAS[name].model_validate(arguments)
