# Integration verification — October 4, 2026

This batch captures accumulated implementation changes in 35 topic-based commits.
Author and committer timestamps were assigned at the user's request across
07:00–22:00 America/Detroit on October 4, 2026. They are organizational metadata,
not a record of when each change was implemented or tested.

Verification applies to the combined working tree, not every intermediate commit.
Each commit also receives staged whitespace checks and Python/JavaScript syntax
checks for its changed files. No claim of cryptographic commit signing is made.

## Results

- `uv run --locked pytest -q`: 151 passed; two dependency deprecation warnings.
- `node --test apps/voice/web/*.test.mjs`: 6 passed.
- `npm --prefix apps/voice/web run build`: passed, including pinned vendor hashes.
- `cmake --build build/mac-debug -j 4`: passed.
- Native CTest: 9 of 10 checks passed across the full run and targeted reruns.
  Camera uplink and rejected-profile checks passed after the camera test was
  updated to explicitly select FRONT through the control socket.
- `hud-media-loopback` remains failing: GStreamer VideoToolbox hardware decoder
  reports `VTDecompressionSessionCreate returned -4`. Reproduced with the live
  HUD stopped. This hardware integration check is unresolved.
- `git diff --check`: passed before commit batching.

These checks do not verify optical output, physical camera placement, real-world
hazard accuracy, or audible playback on the glasses. Generated HUD assets are
included; credentials, local runtime state, recordings, and editor recovery files
are excluded.
