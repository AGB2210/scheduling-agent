"""A real model, run locally through Ollama."""

from ollama import Client, ResponseError

from schedagent.agent import LLM, Reply, ToolCall
from schedagent.tools import PLAIN_TOOLS, Tool

CONTEXT_TOKENS = 8192
MAX_REPLY_TOKENS = 512


def model_options(seed: int = 0) -> dict:
    """The settings sent to the model with every request."""
    return {
        # Temperature 0 and a fixed seed make a run repeatable.
        "temperature": 0,
        "seed": seed,
        "num_ctx": CONTEXT_TOKENS,
        # A tool call needs well under 100 tokens. Without a limit, the model
        # sometimes kept writing one reply for minutes without ever stopping.
        "num_predict": MAX_REPLY_TOKENS,
    }


def tool_schemas(tools: dict[str, Tool] = PLAIN_TOOLS) -> list[dict]:
    """Describe a set of tools in the form the model is told about them."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": tool.description,
                "parameters": tool.args.model_json_schema(),
            },
        }
        for name, tool in tools.items()
    ]


def local_model(
    client: Client, model: str, seed: int = 0, tools: dict[str, Tool] = PLAIN_TOOLS
) -> LLM:
    """Wrap an Ollama model as the kind of function the agent loop calls."""

    def llm(messages: list[dict]) -> Reply:
        try:
            response = client.chat(
                model=model,
                messages=[_to_ollama(message) for message in messages],
                tools=tool_schemas(tools),
                options=model_options(seed),
            )
        except ResponseError as error:
            # Ollama could not use what the model wrote, such as a tool call
            # that is not valid JSON. That is the model's mistake, so it counts
            # as a turn with no tool call instead of stopping the whole run.
            return Reply(text=f"[model error: {error.error}]")
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
