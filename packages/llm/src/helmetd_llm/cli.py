import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from .client import LLM, Finish, Message, ProviderError
from .settings import PROVIDERS, Settings


async def chat(settings: Settings, prompt: str):
    async for event in LLM(settings).stream([Message("user", prompt)]):
        if isinstance(event, str):
            print(event, end="", flush=True)
        elif isinstance(event, Finish) and event.reason == "length":
            print("\n[Output token limit reached]", file=sys.stderr)
    print()


def main():
    parser = argparse.ArgumentParser(description="Stream a response from the selected AI provider")
    parser.add_argument("prompt")
    parser.add_argument("--provider", choices=PROVIDERS)
    parser.add_argument("--model", help="Override the selected provider's model ID")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    try:
        asyncio.run(chat(Settings.from_env(args.provider, args.model), args.prompt))
    except (ValueError, ProviderError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    except KeyboardInterrupt:
        parser.exit(130, "\nStopped.\n")
