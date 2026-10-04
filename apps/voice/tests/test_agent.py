import copy
import json

import httpx
from helmetd_voice.agent import FIRST_MESSAGE, PERSONALITY_TEMPERATURE, PROMPT, configure_agent
from helmetd_voice.tool_specs import TOOLS


def test_sdk_configuration_preserves_voice_auth_model_and_does_not_republish(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "agent-test")
    saved = {
        "agent_id": "agent-test",
        "name": "Helmetd",
        "platform_settings": {"auth": {"enable_auth": True}},
        "conversation_config": {
            "agent": {
                "first_message": "old",
                "language": "en",
                "prompt": {
                    "prompt": "old",
                    "llm": "gemini-3.5-flash",
                    "temperature": 0.3,
                    "tools": [],
                    "tool_ids": [],
                },
            },
            "tts": {"voice_id": "selected-voice", "model_id": "eleven_flash_v2"},
        },
    }
    updates = []

    def respond(request):
        assert request.headers["xi-api-key"] == "test-key"
        assert request.url.path == "/v1/convai/agents/agent-test"
        if request.method == "PATCH":
            data = json.loads(request.content)
            assert "tool_ids" not in data["conversation_config"]["agent"]["prompt"]
            updates.append(copy.deepcopy(data))
            saved["conversation_config"]["agent"].update(data["conversation_config"]["agent"])
            for tool in saved["conversation_config"]["agent"]["prompt"]["tools"]:
                tool["parameters"]["description"] = None  # API adds default fields.
        return httpx.Response(200, json=saved)

    original = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kw: original(**kw, transport=httpx.MockTransport(respond))
    )
    configure_agent()
    configure_agent()
    assert len(updates) == 1
    assert saved["conversation_config"]["tts"]["voice_id"] == "selected-voice"
    assert saved["platform_settings"]["auth"]["enable_auth"]
    agent = saved["conversation_config"]["agent"]
    assert agent["first_message"] == FIRST_MESSAGE
    assert agent["prompt"]["prompt"] == PROMPT
    assert agent["prompt"]["llm"] == "gemini-3.5-flash"
    assert agent["prompt"]["temperature"] == PERSONALITY_TEMPERATURE
    assert {t["name"] for t in agent["prompt"]["tools"]} == {t["name"] for t in TOOLS}
    export = (tmp_path / ".local/copilot/agent-config.json").read_text()
    assert "test-key" not in export
