import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from helmetd_llm.client import LLM
from helmetd_llm.settings import PROVIDERS, Settings

from .voice import required, say, talk


def main():
    parser = argparse.ArgumentParser(
        description="Helmetd live voice, spoken alerts, and LLM gateway"
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("talk", help="Start a private ElevenLabs agent using Mac audio")
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
            talk()
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
    except Exception:
        # Provider/transport exceptions can contain auth URLs and request data.
        parser.exit(
            1, "Voice operation failed; check credentials, connectivity, and audio devices.\n"
        )
