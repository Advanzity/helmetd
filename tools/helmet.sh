#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
exec uv run --locked python tools/start_helmet.py "$@"
