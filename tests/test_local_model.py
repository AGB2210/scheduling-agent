from ollama import ChatResponse, Message

from schedagent.agent import Reply, ToolCall
from schedagent.local_model import CONTEXT_TOKENS, local_model, tool_schemas


class FakeClient:
    """Stands in for Ollama: records the request and gives a canned answer."""

    def __init__(self, message):
        self.message = message
        self.requests = []

    def chat(self, **request):
        self.requests.append(request)
        return ChatResponse(message=self.message)


def tool_call_message(name, **arguments):
    call = Message.ToolCall(
        function=Message.ToolCall.Function(name=name, arguments=arguments)
    )
    return Message(role="assistant", content="", tool_calls=[call])


def test_tool_schemas_describe_all_four_tools():
    schemas = {schema["function"]["name"]: schema["function"] for schema in tool_schemas()}
    assert set(schemas) == {"list_people", "get_busy", "book", "give_up"}
    assert all(schema["type"] == "function" for schema in tool_schemas())
    book = schemas["book"]
    assert book["description"].startswith("Book the meeting.")
    assert set(book["parameters"]["required"]) == {"attendees", "day", "start", "end"}
    assert schemas["list_people"]["parameters"]["properties"] == {}


def test_a_tool_call_from_the_model_becomes_a_reply():
    client = FakeClient(tool_call_message("get_busy", person="Ravi"))
    reply = local_model(client, "some-model")([{"role": "user", "content": "hi"}])
    assert reply == Reply(calls=(ToolCall(name="get_busy", args={"person": "Ravi"}),))


def test_plain_text_from_the_model_becomes_a_reply_with_no_calls():
    client = FakeClient(Message(role="assistant", content="Tuesday looks good."))
    reply = local_model(client, "some-model")([{"role": "user", "content": "hi"}])
    assert reply == Reply(text="Tuesday looks good.")


def test_request_names_the_model_the_tools_and_repeatable_settings():
    client = FakeClient(Message(role="assistant", content="ok"))
    local_model(client, "some-model", seed=7)([{"role": "user", "content": "hi"}])
    request = client.requests[0]
    assert request["model"] == "some-model"
    assert request["tools"] == tool_schemas()
    assert request["options"] == {
        "temperature": 0,
        "seed": 7,
        "num_ctx": CONTEXT_TOKENS,
    }


def test_the_conversation_is_translated_into_ollamas_format():
    client = FakeClient(Message(role="assistant", content="ok"))
    conversation = [
        {"role": "system", "content": "instructions"},
        {"role": "user", "content": "request"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"name": "get_busy", "args": {"person": "Ravi"}}],
        },
        {"role": "tool", "name": "get_busy", "content": "[]"},
    ]
    local_model(client, "some-model")(conversation)
    assert client.requests[0]["messages"] == [
        {"role": "system", "content": "instructions"},
        {"role": "user", "content": "request"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "get_busy", "arguments": {"person": "Ravi"}}}
            ],
        },
        {"role": "tool", "tool_name": "get_busy", "content": "[]"},
    ]
    # Ollama's own message type must accept every one of them.
    for message in client.requests[0]["messages"]:
        Message.model_validate(message)
