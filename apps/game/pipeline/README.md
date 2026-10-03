# Asset authoring snapshot

These scripts and the game's root Blender files preserve the original Shelby
Ride asset pipeline. Runtime exports are committed in `../public/assets/`;
running the game does not require Blender or these scripts.

The scripts retain their original local workspace paths, including
`/Users/david/Documents/Codex/2026-10-01/c`, and use raw geographic/model inputs
under that workspace's `work/` directory. Those raw inputs are not part of this
import. Several scripts overwrite exports in the original project, so review
and update their paths before running them for the monorepo.

`../inspection/` contains existing visual references, not fresh validation of
the import. Source attribution is in the [game README](../README.md).
