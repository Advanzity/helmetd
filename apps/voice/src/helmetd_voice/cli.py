import argparse
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from elevenlabs.core.api_error import ApiError
from helmetd_llm.client import LLM
from helmetd_llm.settings import PROVIDERS, Settings

from .voice import VoiceSessionError, required, say, talk


def main():
    parser = argparse.ArgumentParser(
        description="Helmetd live voice, spoken alerts, and LLM gateway"
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    commands = parser.add_subparsers(dest="command", required=True)
    conversation = commands.add_parser("talk", help="Start a private agent using Mac audio")
    conversation.add_argument("--alerts", action="store_true")
    conversation.add_argument(
        "--macbook", action="store_true", help="Use built-in MacBook microphone and speakers"
    )
    conversation.add_argument(
        "--no-sync", action="store_true", help="Use the existing cloud config"
    )
    conversation.add_argument("--alert-port", type=int, default=8014)
    conversation.add_argument("--seconds", type=int, choices=range(1, 3601), metavar="1..3600")
    commands.add_parser("prepare-alerts", help="Cache the fixed detection phrases")
    commands.add_parser("connect-hazards", help="Connect the Helmetd agent to local Solana tools")
    commands.add_parser("configure-agent", help="Sync the Helmetd personality and copilot actions")
    commands.add_parser("actions", help="Show example things to say to the copilot")
    web_test = commands.add_parser("web-test", help="Mac voice test with browser WebRTC audio")
    web_test.add_argument("--port", type=int, default=8016)
    launch = commands.add_parser("launch", help="Start the HUD and Helmetd copilot together")
    launch.add_argument("--camera", choices=("udp", "test", "none"), default="udp")
    launch.add_argument("--host", default="172.20.10.5")
    launch.add_argument("--preview", action="store_true", help="Show locally without Pi downlink")
    launch.add_argument("--hud-only", action="store_true", help="Start only the local HUD")
    action = commands.add_parser("act", help="Test a local copilot action without the cloud")
    action.add_argument("name")
    action.add_argument("--args", default="{}", help="JSON object of action parameters")
    setup = commands.add_parser("setup-agent", help="Create and save a new private Helmetd agent")
    setup.add_argument("--model", required=True, help="Explicit ElevenLabs hosted LLM ID")
    alerts = commands.add_parser("alerts", help="Speak fresh local HUD detection cues")
    alerts.add_argument("--port", type=int, default=8014)
    alert = commands.add_parser("say", help="Speak a standalone alert or save a WAV")
    alert.add_argument("text")
    alert.add_argument("--output", type=Path)
    gateway = commands.add_parser("serve", help="Start the authenticated Custom LLM endpoint")
    gateway.add_argument("--provider", choices=PROVIDERS)
    gateway.add_argument("--model")
    gateway.add_argument("--host", default="127.0.0.1")
    gateway.add_argument("--port", type=int, default=8013)
    commands.add_parser("doctor", help="Report configuration presence without exposing secrets")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    try:
        if args.command == "talk":
            if not args.no_sync:
                from .agent import configure_agent

                configure_agent()
            talk(args.alerts, args.alert_port, args.seconds, macbook=args.macbook)
        elif args.command == "configure-agent":
            from .agent import configure_agent

            configure_agent()
        elif args.command == "launch":
            from .launch import launch

            launch(args.camera, args.host, args.preview, args.hud_only)
        elif args.command == "web-test":
            import uvicorn

            from .web_test import create_web_app

            print(f"Mac voice test: http://127.0.0.1:{args.port}", flush=True)
            uvicorn.run(create_web_app(), host="127.0.0.1", port=args.port, access_log=False)
        elif args.command == "actions":
            from .tool_specs import EXAMPLES

            print("While the voice session is running, try:")
            for example in EXAMPLES:
                print(f"  {example}")
        elif args.command == "act":
            from .copilot import Copilot

            print(Copilot().call(args.name, json.loads(args.args)))
        elif args.command == "prepare-alerts":
            from .alerts import prepare_alerts

            prepare_alerts()
            print("Detection phrases cached.")
        elif args.command == "setup-agent":
            from .agent import setup_agent

            setup_agent(args.env_file, args.model)
        elif args.command == "connect-hazards":
            from .agent import connect_hazards

            connect_hazards()
        elif args.command == "alerts":
            from .alerts import run_alerts

            run_alerts(args.port)
        elif args.command == "say":
            say(args.text, args.output)
        elif args.command == "serve":
            import uvicorn

            from .server import create_app

            settings = Settings.from_env(args.provider, args.model)
            app = create_app(LLM(settings), required("HELMETD_GATEWAY_TOKEN"))
            print(f"LLM: {settings.provider} / {settings.model}", flush=True)
            uvicorn.run(app, host=args.host, port=args.port, access_log=False)
        else:
            for name in (
                "HELMETD_LLM_PROVIDER",
                "OPENAI_MODEL",
                "GOOGLE_MODEL",
                "ANTHROPIC_MODEL",
                "OPENAI_API_KEY",
                "GOOGLE_API_KEY",
                "ANTHROPIC_API_KEY",
                "HELMETD_GATEWAY_TOKEN",
                "ELEVENLABS_API_KEY",
                "ELEVENLABS_AGENT_ID",
                "ELEVENLABS_VOICE_ID",
                "ELEVENLABS_TTS_MODEL",
            ):
                print(f"{name}: {'set' if os.getenv(name, '').strip() else 'missing'}")
            print("Presence check only; credentials, agent settings, and devices are not verified.")
    except ValueError as exc:
        parser.exit(1, f"Configuration error: {exc}\n")
    except FileExistsError:
        parser.exit(1, "Output file already exists. Choose a new path.\n")
    except KeyboardInterrupt:
        parser.exit(130, "\nStopped.\n")
    except (httpx.ConnectError, httpx.TimeoutException):
        parser.exit(
            1,
            "ElevenLabs is unreachable. The copilot configuration is saved locally. "
            "Retry configure-agent when the connection returns; "
            "launch --hud-only runs the HUD without cloud voice.\n",
        )
    except ApiError as error:
        parser.exit(
            1,
            f"ElevenLabs rejected the request (HTTP {error.status_code}). "
            "Check the account's API permissions and available credits.\n",
        )
    except VoiceSessionError as error:
        parser.exit(1, f"Voice session ended: {error}\n")
    except Exception:
        # Provider/transport exceptions can contain auth URLs and request data.
        parser.exit(
            1, "Voice operation failed; check credentials, connectivity, and audio devices.\n"
        )
