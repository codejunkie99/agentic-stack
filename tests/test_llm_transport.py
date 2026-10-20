"""Offline checks at the real SDK HTTP boundary for the portable LLM helper."""
import json
import sys
from pathlib import Path
from unittest import mock

import anthropic
import openai
import pytest

def http_transport(sdk):
    # Match each SDK's HTTP implementation, including its declared older versions.
    from importlib import import_module

    for cls in sdk.DefaultHttpxClient.__mro__:
        module = cls.__module__.split(".")[0]
        if module in {"httpx", "httpx2"}:
            return import_module(module)
    raise AssertionError("Unknown SDK HTTP transport")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agent" / "harness"))
import llm  # noqa: E402


@pytest.mark.parametrize("region,host", [
    ("global_en", "api.minimax.io"), ("cn_zh", "api.minimaxi.com"),
])
@pytest.mark.parametrize("wire", ["openai", "anthropic"])
@pytest.mark.parametrize("saved,override,expected", [
    (None, None, "MiniMax-M3.1-Flash"),
    ("", None, "MiniMax-M3.1-Flash"),
    ("MiniMax-M3", None, "MiniMax-M3"),
    ("MiniMax-M2.7", None, "MiniMax-M2.7"),
    ("custom-saved", None, "custom-saved"),
    ("MiniMax-M3", "custom-explicit", "custom-explicit"),
    ("MiniMax-M2.7", "MiniMax-M3.1-Flash", "MiniMax-M3.1-Flash"),
])
@pytest.mark.parametrize("multimodal", [False, True])
def test_minimax_serialized_request(region, host, wire, saved, override, expected, multimodal):
    captured = []

    def respond(request):
        captured.append(request)
        if wire == "anthropic":
            body = {
                "id": "msg_fixture", "type": "message", "role": "assistant",
                "model": expected, "stop_reason": "end_turn", "stop_sequence": None,
                "content": [
                    {"type": "thinking", "thinking": "private reasoning", "signature": "fixture"},
                    {"type": "text", "text": "answer"},
                    {"type": "text", "text": "!"},
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        else:
            body = {
                "id": "chat_fixture", "object": "chat.completion", "created": 0,
                "model": expected,
                "choices": [{"index": 0, "finish_reason": "stop", "message": {
                    "role": "assistant", "content": "answer!", "reasoning_content": "private reasoning",
                }}],
            }
        return httpx.Response(200, json=body)

    user = "hello"
    if multimodal:
        if wire == "anthropic":
            user = [
                {"type": "text", "text": "describe"},
                {"type": "image", "source": {"type": "url", "url": "https://example.invalid/image.png"}},
                {"type": "video", "source": {"type": "url", "url": "https://example.invalid/video.mp4"}},
            ]
        else:
            user = [
                {"type": "text", "text": "describe"},
                {"type": "image_url", "image_url": {"url": "https://example.invalid/image.png"}},
                {"type": "video_url", "video_url": {"url": "https://example.invalid/video.mp4"}},
            ]
    environment = {
        "AGENT_PROVIDER": "minimax", "MINIMAX_API_KEY": "fixture-key",
        "AGENT_MINIMAX_REGION": region, "AGENT_MINIMAX_WIRE": wire,
    }
    if saved is not None:
        environment["AGENT_MODEL"] = saved
    sdk = anthropic if wire == "anthropic" else openai
    client_name = "Anthropic" if wire == "anthropic" else "OpenAI"
    real_client = getattr(sdk, client_name)
    httpx = http_transport(sdk)
    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        def factory(**kwargs):
            return real_client(**kwargs, http_client=transport, max_retries=0)

        with mock.patch.dict("os.environ", environment, clear=True), mock.patch.object(sdk, client_name, factory):
            assert llm.call_model("system", user, model=override, max_tokens=1234) == "answer!"

    assert len(captured) == 1
    request = captured[0]
    assert request.url.host == host
    assert request.url.path == ("/anthropic/v1/messages" if wire == "anthropic" else "/v1/chat/completions")
    body = json.loads(request.content)
    assert body["model"] == expected
    assert body["max_tokens"] == 1234
    assert body["temperature"] == 0.3
    assert body["messages"][-1] == {"role": "user", "content": user}
    if wire == "anthropic":
        assert body["system"] == "system"
    else:
        assert body["messages"][0] == {"role": "system", "content": "system"}
    # The helper has no thinking/effort controls: retain API defaults on both wires.
    for field in ("thinking", "reasoning_effort", "output_config", "service_tier", "reasoning_split"):
        assert field not in body


@pytest.mark.parametrize("provider,expected", [
    ("openai", "gpt-4o"), ("anthropic", "claude-sonnet-4-5"),
])
def test_other_provider_defaults_are_unchanged(provider, expected):
    from types import SimpleNamespace

    client = mock.Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))],
    )
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="answer")],
    )
    sdk = openai if provider == "openai" else anthropic
    name = "OpenAI" if provider == "openai" else "Anthropic"
    with mock.patch.dict("os.environ", {"AGENT_PROVIDER": provider}, clear=True):
        with mock.patch.object(sdk, name, return_value=client):
            assert llm.call_model("system", "hello") == "answer"
    create = client.chat.completions.create if provider == "openai" else client.messages.create
    assert create.call_args.kwargs["model"] == expected


def test_conductor_default_reaches_flash_transport(monkeypatch):
    import conductor

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "chat_fixture", "object": "chat.completion", "created": 0,
            "model": "MiniMax-M3.1-Flash",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": "answer",
            }}],
        })

    seats = {
        "memory": lambda *args, **kwargs: ("context", 1),
        "planning": lambda *args: "plan", "capability": lambda *args: [],
    }
    monkeypatch.setattr(conductor, "seat", seats.__getitem__)
    monkeypatch.setattr(conductor, "log_execution", lambda *args: None)
    real_client = openai.OpenAI
    httpx = http_transport(openai)
    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        def factory(**kwargs):
            return real_client(**kwargs, http_client=transport, max_retries=0)

        with mock.patch.dict("os.environ", {"AGENT_PROVIDER": "minimax", "MINIMAX_API_KEY": "fixture-key"}, clear=True):
            with mock.patch.object(openai, "OpenAI", factory):
                assert conductor.run("hello") == "answer"
    assert requests[0]["model"] == "MiniMax-M3.1-Flash"
    assert requests[0]["messages"][-1]["content"] == "hello"
