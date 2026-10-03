# Voice on the Mac

Python sidecar for a live ElevenLabs conversational agent, standalone spoken
alerts, and the HTTP bridge to Helmetd's own LLM layer. Voice networking runs
outside the native tracking and rendering loop.

```text
Mac microphone -> ElevenLabs speech recognition / conversation orchestration
                       |
                       | authenticated HTTPS, streaming text
                       v
              Helmetd gateway on Mac -> packages/llm -> selected AI provider
                       |
                       v
              ElevenLabs voice -> Mac audio output

Alert text -> ElevenLabs TTS -> Mac audio output or a WAV file
```

Helmetd selects the reasoning provider/model. ElevenLabs handles the speech
pipeline and conversational turn taking. Both services receive conversation
content. This first implementation uses the Mac's default microphone and output;
Pi microphone transport, glasses audio routing, HUD event triggers, and tool
execution are still pending. Alerts are standalone commands; stop a live session
before playing one to avoid overlapping audio or feeding it into the microphone.

## Setup

Run from the repository root with Python 3.12–3.14 and `uv` available:

```sh
brew install uv portaudio
uv sync --locked --extra audio
cp -n .env.example .env
uv run helmetd-voice doctor
```

Edit `.env` locally. Set the selected provider's key and model ID, plus the
ElevenLabs values needed for your command. No models are selected implicitly:
use an ID enabled in your provider account. The committed `uv.lock` pins SDKs.
Environment variables take precedence over `.env`; `--env-file PATH` selects
another file. `doctor` reports presence only and never prints credentials.
Microphone permission must be enabled for the terminal/app launching `talk`.

## Select and test the reasoning provider

Set `HELMETD_LLM_PROVIDER` to `openai`, `google`, or `anthropic`. The matching
`OPENAI_MODEL`, `GOOGLE_MODEL`, or `ANTHROPIC_MODEL` supplies the model ID.
Only the selected provider's API key is required. A command override leaves the
saved default unchanged:

```sh
uv run helmetd-llm "Say that the camera is ready." --provider openai
uv run helmetd-llm "Say that the camera is ready." --provider google
uv run helmetd-llm "Say that the camera is ready." --provider anthropic
```

See [the LLM package](../../packages/llm/README.md) for its shared interface.

## Connect ElevenLabs to Helmetd

1. Generate a gateway token with
   `uv run python -c 'import secrets; print(secrets.token_urlsafe(32))'` and save it
   as `HELMETD_GATEWAY_TOKEN` in `.env`.
2. Start `uv run helmetd-voice serve`. It binds to `127.0.0.1:8013` by default.
   `GET /healthz` checks the process; it does not validate provider access.
3. Provide an HTTPS reverse proxy or tunnel to this local port. ElevenLabs runs
   in the cloud and cannot reach `localhost` on the Mac. Tunnel deployment is
   not included. Keep bearer authentication enabled and use a stable URL for
   the agent. The gateway is a single-user bench service, not a multi-tenant API.
4. Create/configure a **private** ElevenLabs agent. Select **Custom LLM**, the
   **Chat Completions** format, and model ID **`helmetd`**. Configure the base URL
   so requests arrive at `https://YOUR-HOST/v1/chat/completions` (normally enter
   `https://YOUR-HOST/v1` when the dashboard appends `/chat/completions`). Store
   the gateway token in the agent's Custom LLM API-key secret; requests must
   carry `Authorization: Bearer <HELMETD_GATEWAY_TOKEN>`.
5. Set the agent's output token limit to **512** to match the default gateway
   maximum, or change both together. Use a text model that supports the agent's
   temperature setting (0–1). Some reasoning models reject temperature; omit it
   in the caller when supported, or select a compatible model.
6. Configure the agent's prompt, first message, language, and voice. Disable
   function/system tools, reasoning summaries, and structured/multimodal output
   for this first text-only bridge. Nonempty tool lists and unsupported message
   types are rejected explicitly.
7. Save its ID as `ELEVENLABS_AGENT_ID`; set `ELEVENLABS_API_KEY` locally. Start:

```sh
uv run --extra audio helmetd-voice talk
```

Keep `serve` running in a separate terminal. Press Ctrl-C to end the conversation.
`talk` uses the agent's published configuration; it does not edit it. To switch
the live agent to Claude, for example, restart the gateway with:

```sh
uv run helmetd-voice serve --provider anthropic
```

The endpoint and agent model alias remain `helmetd`. Provider selection is fixed
for the gateway process and changes after restart. There is no automatic fallback
to another vendor. No paid API request is made merely by starting the gateway.

## Spoken alerts

Set `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, and `ELEVENLABS_TTS_MODEL` to your
chosen voice and a TTS model that supports `pcm_16000` output. An agent ID and LLM
credentials are not required for standalone alerts.

```sh
uv run --extra audio helmetd-voice say "Camera connected. HUD ready."
mkdir -p artifacts
uv run helmetd-voice say "Tracking lost." --output artifacts/tracking-lost.wav
```

WAV export needs no audio device or PyAudio. Output is 16 kHz, mono, signed
16-bit PCM. Existing files are never overwritten; interrupted exports are
removed. The live session's voice is configured separately in the agent.

## Verification

```sh
uv run pytest
uv run ruff check apps/voice packages/llm
uv run ruff format --check apps/voice packages/llm
```

Offline tests exercise the actual provider SDKs against simulated HTTP/SSE,
provider selection, request validation, auth, errors, stream cancellation,
ElevenLabs PCM/WAV handling, and audio cleanup. They do not verify billing,
credentials, account model access, microphone permissions, speech latency, or
the cloud-to-Mac route. After configuration, run one text prompt, one saved alert,
and a short live conversation; interrupt speech and confirm audio stops cleanly.

References: [ElevenLabs Python SDK](https://elevenlabs.io/docs/eleven-agents/libraries/python),
[Custom LLM integration](https://elevenlabs.io/docs/eleven-agents/customization/llm/custom-llm),
[streaming TTS](https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/streaming).
