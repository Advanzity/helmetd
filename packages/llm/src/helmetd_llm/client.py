"""Normalize the three official SDKs to text deltas and an explicit finish event."""

import asyncio
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import aclosing
from dataclasses import dataclass
from typing import Literal

from .settings import Settings


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class Finish:
    reason: Literal["stop", "length"] = "stop"


class ProviderError(RuntimeError):
    """Safe to display: does not contain upstream request bodies or credentials."""


def split_system(messages: Sequence[Message]):
    system = "\n\n".join(m.content for m in messages if m.role == "system")
    turns = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
    return system, turns


class LLM:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str | Finish]:
        if not messages or not any(m.role == "user" for m in messages):
            raise ValueError("At least one user message is required")
        if any(m.role not in {"system", "user", "assistant"} for m in messages):
            raise ValueError("Only system, user, and assistant text messages are supported")
        # A system instruction after dialogue cannot be moved without changing its meaning.
        in_dialogue = False
        for message in messages:
            if message.role == "system" and in_dialogue:
                raise ValueError("System messages must precede dialogue")
            in_dialogue |= message.role != "system"
        limit = self.settings.max_tokens if max_tokens is None else max_tokens
        if not 1 <= limit <= self.settings.max_tokens:
            raise ValueError("Requested token limit exceeds the configured maximum")
        if temperature is not None and not 0 <= temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")
        adapter = getattr(self, f"_{self.settings.provider}")
        try:
            # A gateway primes this generator in one task and consumes it in another.
            # Never leave a task-bound timeout context open across a yield.
            deadline = time.monotonic() + self.settings.timeout
            async with aclosing(adapter(messages, limit, temperature)) as events:
                saw_text = False
                while True:
                    try:
                        async with asyncio.timeout(max(0, deadline - time.monotonic())):
                            event = await anext(events)
                    except StopAsyncIteration:
                        return
                    if isinstance(event, str):
                        saw_text |= bool(event)
                    elif not saw_text:
                        raise ProviderError("Provider returned no speakable text")
                    yield event
        except ProviderError:
            raise
        except TimeoutError:
            raise ProviderError("LLM request timed out") from None
        except Exception:
            raise ProviderError(
                f"{self.settings.provider} request failed; check credentials, model, and quota"
            ) from None

    async def _openai(self, messages, limit, temperature):
        from openai import AsyncOpenAI, omit

        async with AsyncOpenAI(
            api_key=self.settings.api_key, timeout=self.settings.timeout, max_retries=0
        ) as client:
            async with client.responses.stream(
                model=self.settings.model,
                input=[{"role": m.role, "content": m.content} for m in messages],
                max_output_tokens=limit,
                temperature=temperature if temperature is not None else omit,
                store=False,
            ) as stream:
                async for event in stream:
                    if event.type in {"response.output_text.delta", "response.refusal.delta"}:
                        yield event.delta
                    elif event.type == "response.completed":
                        yield Finish()
                        return
                    elif event.type == "response.incomplete":
                        details = event.response.incomplete_details
                        if details and details.reason == "max_output_tokens":
                            yield Finish("length")
                            return
                        raise ProviderError("OpenAI response was incomplete")
                    elif event.type in {"error", "response.failed"}:
                        raise ProviderError("OpenAI could not complete the response")
        raise ProviderError("OpenAI stream ended without a completion event")

    async def _anthropic(self, messages, limit, temperature):
        from anthropic import AsyncAnthropic, omit

        system, turns = split_system(messages)
        async with AsyncAnthropic(
            api_key=self.settings.api_key, timeout=self.settings.timeout, max_retries=0
        ) as client:
            async with client.messages.stream(
                model=self.settings.model,
                system=system or omit,
                messages=turns,
                max_tokens=limit,
                temperature=temperature if temperature is not None else omit,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
                if final.stop_reason == "max_tokens":
                    yield Finish("length")
                elif final.stop_reason in {"end_turn", "stop_sequence", "refusal"}:
                    yield Finish()
                else:
                    raise ProviderError("Claude did not complete a text response")

    async def _google(self, messages, limit, temperature):
        from google import genai
        from google.genai import types

        system, turns = split_system(messages)
        client = genai.Client(
            api_key=self.settings.api_key,
            http_options=types.HttpOptions(
                timeout=int(self.settings.timeout * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        try:
            async with client.aio as async_client:
                stream = await async_client.models.generate_content_stream(
                    model=self.settings.model,
                    contents=[
                        types.Content(
                            role="model" if m["role"] == "assistant" else "user",
                            parts=[types.Part.from_text(text=m["content"])],
                        )
                        for m in turns
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=system or None,
                        max_output_tokens=limit,
                        candidate_count=1,
                        temperature=temperature,
                    ),
                )
                async with aclosing(stream):
                    async for chunk in stream:
                        if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                            raise ProviderError("Gemini blocked this request")
                        for candidate in chunk.candidates or []:
                            if candidate.content:
                                for part in candidate.content.parts or []:
                                    if part.text and not part.thought:
                                        yield part.text
                            if candidate.finish_reason:
                                reason = candidate.finish_reason.value
                                if reason not in {"STOP", "MAX_TOKENS"}:
                                    raise ProviderError("Gemini did not complete a text response")
                                yield Finish("length" if reason == "MAX_TOKENS" else "stop")
                                return
            raise ProviderError("Gemini stream ended without a completion event")
        finally:
            client.close()
