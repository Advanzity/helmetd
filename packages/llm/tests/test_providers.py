"""Exercise real SDK request serialization and SSE parsing without paid API calls."""

import json

import httpx
import pytest
from helmetd_llm.client import LLM, Finish, Message, ProviderError
from helmetd_llm.settings import Settings

MESSAGES = [
    Message("system", "Be concise."),
    Message("user", "Hello"),
    Message("assistant", "Hi"),
    Message("user", "Status?"),
]


def sse(events):
    return "".join(
        (f"event: {e['type']}\n" if "type" in e else "") + f"data: {json.dumps(e)}\n\n"
        for e in events
    )


def openai_events(status="completed"):
    return [
        {
            "type": "response.created",
            "sequence_number": 0,
            "response": {
                "id": "resp_1",
                "object": "response",
                "created_at": 1,
                "status": "in_progress",
                "output": [],
            },
        },
        {
            "type": "response.output_item.added",
            "sequence_number": 1,
            "output_index": 0,
            "item": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "status": "in_progress",
                "content": [],
            },
        },
        {
            "type": "response.content_part.added",
            "sequence_number": 2,
            "item_id": "msg_1",
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": "", "annotations": [], "logprobs": []},
        },
        {
            "type": "response.output_text.delta",
            "delta": "Ready",
            "sequence_number": 3,
            "item_id": "msg_1",
            "output_index": 0,
            "content_index": 0,
            "logprobs": [],
        },
        {
            "type": f"response.{status}",
            "sequence_number": 1,
            "response": {
                "id": "resp_1",
                "object": "response",
                "created_at": 1,
                "status": status,
                "output": [],
                "incomplete_details": {"reason": "max_output_tokens"}
                if status == "incomplete"
                else None,
            },
        },
    ]


def anthropic_events():
    return [
        {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "test-model",
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 5, "output_tokens": 0},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Ready"},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": 1},
        },
        {"type": "message_stop"},
    ]


def google_events():
    return [
        {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": "private thought", "thought": True}, {"text": "Ready"}],
                    }
                }
            ]
        },
        {"candidates": [{"finishReason": "STOP"}]},
    ]


def mock_provider(monkeypatch, provider, events, requests, status=200):
    def respond(request):
        requests.append(request)
        return httpx.Response(
            status, text=sse(events), headers={"content-type": "text/event-stream"}
        )

    transport = httpx.MockTransport(respond)
    if provider == "openai":
        import openai

        original = openai.AsyncOpenAI
        monkeypatch.setattr(
            openai,
            "AsyncOpenAI",
            lambda **kw: original(**kw, http_client=httpx.AsyncClient(transport=transport)),
        )
    elif provider == "anthropic":
        import anthropic

        original = anthropic.AsyncAnthropic
        monkeypatch.setattr(
            anthropic,
            "AsyncAnthropic",
            lambda **kw: original(**kw, http_client=httpx.AsyncClient(transport=transport)),
        )
    else:
        from google import genai

        original = genai.Client

        def client(**kw):
            kw["http_options"].httpx_async_client = httpx.AsyncClient(transport=transport)
            return original(**kw)

        monkeypatch.setattr(genai, "Client", client)


@pytest.mark.parametrize(
    "provider,events",
    [
        ("openai", openai_events()),
        ("anthropic", anthropic_events()),
        ("google", google_events()),
    ],
)
async def test_sdk_round_trip_and_message_translation(monkeypatch, provider, events):
    requests = []
    mock_provider(monkeypatch, provider, events, requests)
    llm = LLM(Settings(provider, "test-model", "secret", max_tokens=256))
    output = [item async for item in llm.stream(MESSAGES, temperature=0.5)]
    assert output == ["Ready", Finish()]
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    if provider == "openai":
        assert requests[0].url.path == "/v1/responses"
        assert body["input"][0] == {"role": "system", "content": "Be concise."}
        assert body["max_output_tokens"] == 256
        assert body["store"] is False
        assert body["temperature"] == 0.5
    elif provider == "anthropic":
        assert requests[0].url.path == "/v1/messages"
        assert body["system"] == "Be concise."
        assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
        assert body["max_tokens"] == 256
    else:
        assert "streamGenerateContent" in requests[0].url.path
        assert body["systemInstruction"]["parts"] == [{"text": "Be concise."}]
        assert [m["role"] for m in body["contents"]] == ["user", "model", "user"]
        assert body["generationConfig"]["maxOutputTokens"] == 256


@pytest.mark.parametrize("provider", ["openai", "google", "anthropic"])
async def test_credentials_error_is_sanitized_and_not_retried(monkeypatch, provider):
    requests = []
    mock_provider(
        monkeypatch, provider, [{"error": "secret upstream detail"}], requests, status=401
    )
    llm = LLM(Settings(provider, "test-model", "super-secret"))
    with pytest.raises(ProviderError) as error:
        _ = [item async for item in llm.stream(MESSAGES)]
    assert "secret" not in str(error.value)
    assert len(requests) == 1


async def test_output_limit_is_not_reported_as_complete(monkeypatch):
    mock_provider(monkeypatch, "openai", openai_events("incomplete"), [])
    result = [item async for item in LLM(Settings("openai", "m", "key")).stream(MESSAGES)]
    assert result[-1] == Finish("length")


async def test_premature_stream_is_error(monkeypatch):
    mock_provider(monkeypatch, "openai", openai_events()[:-1], [])
    with pytest.raises(ProviderError, match="without a completion"):
        _ = [item async for item in LLM(Settings("openai", "m", "key")).stream(MESSAGES)]


async def test_blocked_gemini_is_error(monkeypatch):
    mock_provider(monkeypatch, "google", [{"promptFeedback": {"blockReason": "SAFETY"}}], [])
    with pytest.raises(ProviderError, match="blocked"):
        _ = [item async for item in LLM(Settings("google", "m", "key")).stream(MESSAGES)]


def test_provider_switch_uses_its_own_model_and_key(monkeypatch):
    monkeypatch.setenv("HELMETD_LLM_PROVIDER", "google")
    monkeypatch.setenv("GOOGLE_MODEL", "gemini-test")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-secret")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    assert Settings.from_env().model == "gemini-test"
    override = Settings.from_env("anthropic")
    assert override.model == "claude-test"
    assert override.api_key == "anthropic-secret"
    assert "secret" not in repr(override)


def test_missing_key_does_not_fall_back(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_MODEL", "gemini-test")
    monkeypatch.setenv("OPENAI_API_KEY", "available")
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        Settings.from_env("google")
