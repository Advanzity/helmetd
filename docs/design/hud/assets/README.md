# Generated HUD symbols

`hud-symbols-v1.png` was generated with the built-in imagegen tool. Eight symbols in a 4-column, 2-row atlas: amber left/right/rear/person cues; pale-cyan left/right navigation; white camera and microphone.

Status: integrated into the native Metal HUD at user request. The original atlas is preserved. Texture mode 7 suppresses low-intensity halo pixels with a smooth brightness mask at render time; mipmapped sampling smooths scaled icons. Used for directional detection, turns, camera labels and microphone state.

Prompt: Create a transparent production HUD sprite atlas for Helmetd motorcycle AR glasses, 1536×1024, four columns and two rows, eight isolated symbols with generous padding. Amber left/right open chevrons, paired downward chevrons, person caution symbol; pale-cyan left/right turn arrows, white outline camera and microphone. Premium restrained automotive optics, subtle internal bevel, crisp antialiased silhouettes, no labels, panels, shadows, haze or bloom.

Refinement prompt: Preserve the eight symbols and positions. Remove all background and halos, including openings inside camera and microphone. Real alpha outside silhouettes. White/silver icons, pale cyan arrows, amber warnings, bevel confined inside silhouettes. No aura, bloom, shadow, fog or surrounding light.

## White notification and utility icons
Generated with built-in imagegen. `notification-white-v1.png` is the speech bubble used alongside HUD notification text. `utility-icons-white-v1.png` contains phone, music, location, recording, Wi-Fi, battery, settings, and close symbols; these are saved assets, not connected feature implementations.

Notification prompt: One premium white rounded speech bubble with three dots, subtle internal silver bevel, crisp antialiased strokes readable at 24px, real transparent background and interior, no glow/shadows/text/backdrop.
Utility prompt: Eight white/silver icons in a four-column two-row atlas: phone, music, location, recording; Wi-Fi, half-full battery, settings, close. Moderate rounded strokes, subtle internal bevel, transparent background and interiors, no labels, shadows, bloom, haze or blue color.
