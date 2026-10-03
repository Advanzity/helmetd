"""Text-only OpenAI-compatible gateway for an ElevenLabs Custom LLM agent."""

import json
import secrets
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from helmetd_llm.client import LLM, Finish, Message, ProviderError
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TextMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=65536)
    name: str | None = None


class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: Literal["helmetd"] = "helmetd"
    messages: list[TextMessage] = Field(min_length=1, max_length=128)
    stream: bool = True
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    max_completion_tokens: int | None = Field(default=None, ge=1, le=8192)
    # Accepted ElevenLabs metadata. No caller-supplied provider keys or endpoints.
    user: str | None = None
    user_id: str | None = None
    elevenlabs_extra_body: dict | None = None
    temperature: float | None = Field(default=None, ge=0, le=1)
    tools: list = Field(default_factory=list, max_length=0)
    tool_choice: Literal["none"] | None = None
    n: Literal[1] = 1
    stream_options: dict | None = None

    @model_validator(mode="after")
    def validate_dialogue(self):
        if not any(m.role == "user" for m in self.messages):
            raise ValueError("At least one user message is required")
        dialogue = False
        for message in self.messages:
            if message.role == "system" and dialogue:
                raise ValueError("System messages must precede dialogue")
            dialogue |= message.role != "system"
        if self.max_tokens is not None and self.max_completion_tokens is not None:
            raise ValueError("Use only one output token limit")
        return self


def event(data):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def create_app(llm: LLM, token: str) -> FastAPI:
    if len(token) < 32 or token != token.strip():
        raise ValueError(
            "HELMETD_GATEWAY_TOKEN must contain at least 32 characters, no edge spaces"
        )
    app = FastAPI(title="Helmetd LLM gateway", docs_url=None, redoc_url=None, openapi_url=None)
    bearer = HTTPBearer(auto_error=False)

    def authenticate(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None or not secrets.compare_digest(
            credentials.credentials.encode(), token.encode()
        ):
            raise HTTPException(
                401, "Invalid gateway token", headers={"WWW-Authenticate": "Bearer"}
            )

    @app.get("/healthz")
    async def health():
        return {"status": "ok"}

    @app.post("/v1/chat/completions", dependencies=[Depends(authenticate)])
    async def completion(body: CompletionRequest):
        limit = body.max_completion_tokens or body.max_tokens or llm.settings.max_tokens
        if limit > llm.settings.max_tokens:
            raise HTTPException(422, "Requested token limit exceeds HELMETD_LLM_MAX_TOKENS")
        stream = llm.stream(
            [Message(m.role, m.content) for m in body.messages],
            max_tokens=limit,
            temperature=body.temperature,
        )
        # Prime the provider before sending HTTP 200 so startup failures are real errors.
        try:
            first = await anext(stream)
        except (ProviderError, StopAsyncIteration):
            await stream.aclose()
            raise HTTPException(
                502, "LLM unavailable; check provider configuration or quota"
            ) from None
        except BaseException:
            await stream.aclose()
            raise

        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())

        def chunk(delta, reason=None):
            return {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "helmetd",
                "choices": [{"index": 0, "delta": delta, "finish_reason": reason}],
            }

        async def events() -> AsyncIterator[str | Finish]:
            async with aclosing(stream):
                yield first
                async for item in stream:
                    yield item

        if not body.stream:
            text = []
            reason = None
            try:
                async with aclosing(events()) as source:
                    async for item in source:
                        if isinstance(item, Finish):
                            reason = item.reason
                        else:
                            text.append(item)
            except ProviderError:
                raise HTTPException(502, "LLM generation failed") from None
            if reason is None:
                raise HTTPException(502, "LLM stream ended prematurely")
            return {
                "id": completion_id,
                "object": "chat.completion",
                "created": created,
                "model": "helmetd",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "".join(text)},
                        "finish_reason": reason,
                    }
                ],
            }

        async def sse():
            try:
                async with aclosing(events()) as source:
                    yield event(chunk({"role": "assistant"}))
                    async for item in source:
                        if isinstance(item, Finish):
                            yield event(chunk({}, item.reason))
                            yield "data: [DONE]\n\n"
                            return
                        yield event(chunk({"content": item}))
                    raise ProviderError("Stream ended prematurely")
            except ProviderError:
                # A failure after headers must not masquerade as a completed answer.
                yield event(
                    {"error": {"message": "LLM generation failed", "type": "provider_error"}}
                )
                yield "data: [DONE]\n\n"
            finally:
                await stream.aclose()

        return StreamingResponse(
            sse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
