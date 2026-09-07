from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ProviderResult:
    text: str
    tool_calls: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    simulated: bool = False


class ModelProvider(Protocol):
    name: str
    simulated: bool

    async def complete(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
        model: str,
    ) -> ProviderResult: ...


class SpaceXAIProvider:
    name = "spacexai"
    simulated = False

    def __init__(self, api_key: str, base_url: str = "https://api.x.ai/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url

    async def complete(self, *, system: str, user: str, tools: list[dict[str, Any]], model: str) -> ProviderResult:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=tools or None,
            temperature=0,
        )
        choice = response.choices[0]
        calls = []
        if choice.message.tool_calls:
            import json

            for call in choice.message.tool_calls:
                calls.append(
                    {
                        "name": call.function.name,
                        "arguments": json.loads(call.function.arguments or "{}"),
                    }
                )
        usage = response.usage
        return ProviderResult(
            text=choice.message.content or "",
            tool_calls=calls,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            model=model,
            provider=self.name,
        )


class AnthropicProvider:
    name = "anthropic"
    simulated = False

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def complete(self, *, system: str, user: str, tools: list[dict[str, Any]], model: str) -> ProviderResult:
        import json

        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        converted = [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
            }
            for t in tools
        ]
        response = await client.messages.create(
            model=model,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=converted or None,
        )
        text = ""
        calls: list[dict[str, Any]] = []
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                calls.append({"name": block.name, "arguments": block.input})
        return ProviderResult(
            text=text,
            tool_calls=calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=model,
            provider=self.name,
        )
