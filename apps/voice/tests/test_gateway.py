import asyncio
import json

import httpx
import pytest
from helmetd_llm.client import LLM, Finish, ProviderError
from helmetd_llm.settings import Settings
from helmetd_voice.server import create_app

TOKEN = "t" * 32
BODY = {"model": "helmetd", "messages": [{"role": "user", "content": "Status?"}], "stream": True}


class FakeLLM:
    settings = Settings("openai", "test-model", "test-key")

    def __init__(self, events=None):
        self.events = ["Hello ", "world", Finish()] if events is None else events
        self.called = False
        self.closed = False

    async def stream(self, messages, **kwargs):
        self.called = True
        try:
            for item in self.events:
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            self.closed = True


async def request(llm, body=None, token=TOKEN):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(llm, TOKEN)), base_url="http://test"
    ) as client:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return await client.post(
            "/v1/chat/completions", json=BODY if body is None else body, headers=headers
        )


@pytest.mark.parametrize("token", [None, "wrong"])
async def test_unauthorized_does_not_call_provider(token):
    llm = FakeLLM()
    assert (await request(llm, token=token)).status_code == 401
    assert not llm.called


async def test_stream_has_valid_chunks_finish_and_done():
    llm = FakeLLM()
    response = await request(llm)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    data = [line.removeprefix("data: ") for line in response.text.splitlines() if line]
    assert data[-1] == "[DONE]"
    chunks = [json.loads(line) for line in data[:-1]]
    assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    assert "".join(c["choices"][0]["delta"].get("content", "") for c in chunks) == "Hello world"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    assert len({chunk["id"] for chunk in chunks}) == 1
    assert llm.closed


async def test_non_streaming_and_length():
    llm = FakeLLM(["Truncated", Finish("length")])
    response = await request(llm, {**BODY, "stream": False})
    assert response.json()["choices"][0]["finish_reason"] == "length"
    assert response.json()["choices"][0]["message"]["content"] == "Truncated"


@pytest.mark.parametrize(
    "events,expected_status",
    [
        ([ProviderError("secret")], 502),
        (["Partial", ProviderError("secret")], 200),
        ([], 502),
    ],
)
async def test_provider_errors_are_not_successful_completions(events, expected_status):
    llm = FakeLLM(events)
    response = await request(llm)
    assert response.status_code == expected_status
    assert "secret" not in response.text
    assert '"finish_reason": "stop"' not in response.text
    assert llm.closed


@pytest.mark.parametrize(
    "change",
    [
        {"tools": [{"type": "function"}]},
        {"model": "unconfigured-expensive-model"},
        {"messages": [{"role": "tool", "content": "x"}]},
        {"messages": [{"role": "user", "content": [{"type": "image_url"}]}]},
        {"max_tokens": 8000},
        {"temperature": 2},
        {"max_tokens": 100, "max_completion_tokens": 100},
        {"messages": [{"role": "user", "content": "x"}, {"role": "system", "content": "y"}]},
    ],
)
async def test_unsupported_requests_rejected_before_provider(change):
    llm = FakeLLM()
    response = await request(llm, {**BODY, **change})
    assert response.status_code == 422
    assert not llm.called


async def test_stream_cancellation_releases_provider():
    # Drive the ASGI disconnect event while generation is waiting for its next token.
    closed = asyncio.Event()

    class SlowLLM(LLM):
        async def _openai(self, *args, **kwargs):
            try:
                yield "First"
                await asyncio.Event().wait()
            finally:
                closed.set()

    app = create_app(SlowLLM(Settings("openai", "test-model", "test-key")), TOKEN)
    started = asyncio.Event()
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": json.dumps(BODY).encode(), "more_body": False}
        await started.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body":
            started.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "method": "POST",
        "path": "/v1/chat/completions",
        "query_string": b"",
        "headers": [
            (b"content-type", b"application/json"),
            (b"authorization", f"Bearer {TOKEN}".encode()),
        ],
    }
    await asyncio.wait_for(app(scope, receive, send), timeout=2)
    assert closed.is_set()


async def test_deadline_survives_priming_and_asgi_task_handoff():
    closed = False

    class SlowLLM(LLM):
        async def _openai(self, *args, **kwargs):
            nonlocal closed
            try:
                yield "First"
                await asyncio.Event().wait()
            finally:
                closed = True

    llm = SlowLLM(Settings("openai", "test-model", "test-key", timeout=0.05))
    response = await asyncio.wait_for(request(llm), timeout=2)
    assert response.status_code == 200
    assert "provider_error" in response.text
    assert '"finish_reason": "stop"' not in response.text
    assert closed
