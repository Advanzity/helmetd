#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
exec sh tools/voice.sh launch "$@"
