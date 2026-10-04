#!/bin/sh
# Prefer the separate ignored voice configuration when present.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
voice_env_file=.env
if [ -f .local/elevenlabs.env ]; then voice_env_file=.local/elevenlabs.env; fi
if [ "$#" -eq 0 ]; then set -- talk --alerts; fi
exec uv run --extra audio helmetd-voice --env-file "$voice_env_file" "$@"
