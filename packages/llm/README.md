# Shared LLM interface

Python package for Helmetd-owned reasoning. Three adapters use the official
SDKs: OpenAI Responses, Google Gemini `generate_content_stream`, and Anthropic
Claude Messages. The caller supplies the conversation history; no provider-side
session ID is required. The gateway lives in `apps/voice` so this package can
also be used independently.

```python
from helmetd_llm.client import LLM, Message, Finish
from helmetd_llm.settings import Settings

# Environment must already be loaded; CLI commands load the chosen .env file.
llm = LLM(Settings.from_env())
async for event in llm.stream(
    [
        Message("system", "You are Helmetd. Keep spoken replies brief."),
        Message("user", "Are you ready?"),
    ]
):
    if isinstance(event, str):
        print(event, end="", flush=True)
    elif isinstance(event, Finish):
        print(f"\nFinished: {event.reason}")
```

| Provider setting | Model variable | Credential variable |
| --- | --- | --- |
| `openai` | `OPENAI_MODEL` | `OPENAI_API_KEY` |
| `google` | `GOOGLE_MODEL` | `GOOGLE_API_KEY` |
| `anthropic` | `ANTHROPIC_MODEL` | `ANTHROPIC_API_KEY` |

Choose with `HELMETD_LLM_PROVIDER` or a CLI `--provider` override. `--model` can
override the corresponding model ID for that command. No default model or
cross-provider fallback is supplied; missing configuration fails before a call.
This uses the Gemini Developer API, not Vertex AI.

The first interface supports system instructions followed by user/assistant text,
streamed text deltas, optional temperature (0–1 when the model supports it), and
completion reasons `stop` or `length`. System instructions and assistant roles
are mapped to each SDK's native representation. Images, tool calls, and reasoning
content are outside this interface. Gemini thought parts are excluded; OpenAI
refusal text remains a speakable response. Provider errors never include raw
upstream bodies or credential values.

`HELMETD_LLM_MAX_TOKENS` defaults to 512 (allowed 1–8192).
`HELMETD_LLM_TIMEOUT_SECONDS` defaults to 60 and bounds the whole generation.
Explicit model output limits can include reasoning tokens, so some reasoning
models need a larger budget to produce speech. Automatic SDK retries are disabled;
a failed turn is surfaced to the caller. OpenAI requests set `store=False`.
This is not a guarantee about any provider's logging or retention policy.

Run `uv run helmetd-llm "Hello" --provider google` from the repository root.
For live speech and the HTTP bridge, see [voice setup](../../apps/voice/README.md).

References: [OpenAI streaming](https://developers.openai.com/api/docs/guides/streaming-responses),
[Google Gen AI SDK](https://googleapis.github.io/python-genai/),
[Claude streaming](https://platform.claude.com/docs/en/build-with-claude/streaming).
