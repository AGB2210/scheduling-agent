"""A real model, run locally through Ollama."""

from ollama import Client

from schedagent.agent import LLM, Reply, ToolCall
from schedagent.tools import TOOLS

CONTEXT_TOKENS = 8192


def tool_schemas() -> list[dict]:
    """Describe every tool in the form the model is told about them."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": tool.description,
                "parameters": tool.args.model_json_schema(),
            },
        }
        for name, tool in TOOLS.items()
    ]


def local_model(client: Client, model: str, seed: int = 0) -> LLM:
    """Wrap an Ollama model as the kind of function the agent loop calls."""

    def llm(messages: list[dict]) -> Reply:
        response = client.chat(
            model=model,
            messages=[_to_ollama(message) for message in messages],
            tools=tool_schemas(),
            # Temperature 0 and a fixed seed make a run repeatable.
            options={"temperature": 0, "seed": seed, "num_ctx": CONTEXT_TOKENS},
        )
        message = response.message
        calls = tuple(
            ToolCall(name=call.function.name, args=dict(call.function.arguments))
            for call in message.tool_calls or []
        )
        return Reply(text=message.content or "", calls=calls)

    return llm


def _to_ollama(message: dict) -> dict:
    """Translate one of the loop's messages into Ollama's format."""
    if message["role"] == "tool":
        return {
            "role": "tool",
            "tool_name": message["name"],
            "content": message["content"],
        }
    if message["role"] == "assistant":
        return {
            "role": "assistant",
            "content": message["content"],
            "tool_calls": [
                {"function": {"name": call["name"], "arguments": call["args"]}}
                for call in message["tool_calls"]
            ],
        }
    return message
