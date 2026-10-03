# Shelby Ride — Hall Road / M‑53

Imported into the helmetd monorepo on 2026-10-03 from the existing local
`shelby-ride` project. Game source and runtime behavior are preserved; the
game-to-HUD adapter is not implemented yet. Run the commands below from
`apps/game`.

The import includes the building tile manifest and all referenced tiles. The
unused legacy `public/assets/buildings.glb` mesh, installed dependencies, build
output, and Blender backup files are excluded. Source attribution and licenses
are retained below and in `references/`.

Playable local motorcycle prototype using real Shelby Township / Utica road geometry, USGS elevation, and SEMCOG/OSM building footprints. The playable area is a 3.6 × 3.6 km square centered on 42.6295° N, 83.0245° W. It includes Hall Road, the M‑53 interchange, freeway segments, and nearby streets.

## Run

```sh
npm ci
npm run dev -- --port 5173
```

Open http://127.0.0.1:5173 and click **Click to ride**. A desktop browser with WebGL2 is required. Use headphones for the synthesized engine sound. `npm run build` creates the static site in `dist/`; serve that directory with a local HTTP server, not by double-clicking its HTML file.

## Controls

| Action | Keyboard |
|---|---|
| Throttle / combined brake | W / S or ↑ / ↓ |
| Steer | A / D or ← / → |
| Shift down / up | Q / E |
| Clutch | Shift |
| Rear brake | Space |
| Chase / cinematic / helmet / cockpit | C |
| Recover / reset | R |
| Pause | P |
| Settings | Esc |

Settings include Hall Road or M‑53 starts, manual/automatic transmission, audio mute, and rendering quality. Standard gamepad mapping supports triggers, left stick, A/B shifting, and Y camera selection. Mobile touch driving is not implemented.

## What is implemented

- Fixed 120 Hz motorcycle dynamics with mass, a torque curve, six actual ratios plus neutral, launch clutch assistance, engine braking, drag, traction limits, braking, slip, lean response, suspension approximation, and crashes/reset.
- Four camera modes, a live cockpit display, rotating wheels, brake light, headlight, minimap, and a compact MPH/RPM/gear HUD.
- Continuous AudioWorklet combustion synthesis with a 270/450-degree twin firing pattern, changing RPM/load, ignition cuts, wind, intake, and slip layers.
- Geographic road surfaces, lane markings, bridge decks, rail barriers, instanced lamps, buildings, background vegetation, basic lane-following traffic, surface grip changes, and pooled dust/smoke.
- PBR assets exported from Blender, separate animated parts, authored material responses, normal and roughness maps, daylight environment reflections, shadows, fog, bloom, and tone mapping.

## Important limits

This is a working prototype, not a finished photorealistic recreation or a validated vehicle simulator. The motorcycle/rider still need art refinement for the requested close-up production standard. Façades, street furniture placement, signs, bridge clearances and supports are approximated; the data does not supply surveyed façades or precise engineering geometry. Road widths use OSM lane counts and a standard lane-width assumption. The raw DEM is sampled to a 15 m runtime grid. Older building/elevation records may not match current construction. The SEMCOG query was limited to 2,000 records; local OSM footprints supplement it.

Physics uses a single-track approximation with assisted balance, not a full rigid-body tire/contact solver. Crash motion is simplified and does not include a rider ragdoll. Collisions cover building footprints, traffic and rail barriers; small props, curbs, overhead structures and detailed building surfaces are not all collision-complete. Traffic has basic road continuity and motorcycle proximity response, not a complete traffic-signal or multi-vehicle avoidance system. Engine audio is synthesized, not a measured/sample-based reproduction of a real engine. No night/weather system is included.

## Assets and inspection

`motorcycle.blend` and `sedan.blend` are editable authoring files. `public/assets/*.glb` are runtime exports. `inspection/` contains multi-angle Blender renders. `pipeline/` contains the authoring and processing scripts. These scripts retain local workspace paths; the game itself has no absolute filesystem-path dependency. Raw geographic and human source inputs are retained in the workspace's `work/` directory, outside the runtime package.

The motorcycle reference sheet in `references/sportbike-concept.png` was generated with the built-in image-generation tool. Prompt: photorealistic multiview modeling sheet for an original pearl-white/graphite 700cc sport motorcycle, 1.40 m wheelbase, 0.60 m wheels, 0.83 m seat, and a naturally posed 1.78 m rider, with mechanical detail insets. It is a design guide, not evidence of a manufactured vehicle or a photograph of the final mesh.

## Sources and licenses

- OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright — local road/land-use/building geometry from the official map API, retrieved 2026-10-01.
- SEMCOG building footprints (April 2019): https://gis.semcog.org/server/rest/services/hosted/Building_Footprints/FeatureServer/14 — footprints and median heights; interpreted in feet and converted to meters. Review the source's terms before broader redistribution.
- USGS 3DEP: `USGS_one_meter_x33y473_MI_31Co_Macomb_2016.tif`, from https://apps.nationalmap.gov/downloader/ — public-domain terrain source.
- USGS National Map imagery service: https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer — local aerial backdrop. The downloadable Macomb 2024 MrSID archive was acquired but not used because the installed raster tools cannot decode it.
- Poly Haven, CC0: https://polyhaven.com/a/asphalt_02 and https://polyhaven.com/a/tree_small_02 — asphalt PBR maps and tree geometry/textures; tree optimized and rendered into a distant-tree image in Blender.
- MakeHuman Community, CC0 core assets: https://static.makehumancommunity.org/about/license.html — human base topology, default skeleton and skinning weights. License copied to `references/makehuman-LICENSE.md`.
- Three.js (MIT), Vite (MIT), and their dependency licenses remain with their packages. Google Fonts serves Manrope and Barlow Condensed, with system-font fallback.

## Validation

`npm test` checks gear/RPM coupling, neutral, acceleration/braking, lean direction, geographic start points, building collision, road normals, and the actual audio-worklet output. `npm run build` checks the production bundle. Browser inspection additionally checks asset loading, console errors, HUD composition, and rendered geometry. Gamepad support has not been tested with physical hardware. No claim of a measured stable frame rate is made.

### Scenery refinement

Added 2K Poly Haven `brick_wall_001` base color, normal and roughness textures; `aerial_grass_rock` ground textures; and `evening_road_01_puresky` HDR lighting (all CC0). The settings menu now offers golden evening and blue hour, with a local pool of street spotlights. Mapped parking polygons come from the same OpenStreetMap extract. Commercial frontage details on 63 larger buildings are authored in Blender at meter scale and grouped by map tile and material: stone surrounds, glazing mullions, doors and handles, canopies, sidewalk joints and rooftop air handlers. These details are interpretive, not a survey of individual businesses. Trees use actual mesh instances near the camera and upright image impostors farther away.

Storefront names are fictional illustrative signs. Parking bay markings and parked-car placements are approximations within mapped lots.

### 15–25 Mile corridor and traffic

The riding corridor now extends from 15 Mile to 25 Mile Road around Van Dyke/M‑53. Start locations are available in Settings. Expanded roads, building footprints and 140 signal nodes come from OpenStreetMap; additional terrain comes from the USGS 3DEP Elevation ImageServer. Road widths use mapped lane counts with class-based lane/shoulder estimates because explicit width measurements were absent in this extract. M‑53 pavement separates 3.65 m travel lanes, a 1.2 m inner shoulder and a 3 m outer shoulder. These are modeling assumptions, not surveyed as-built dimensions.

Traffic follows directed road connections, slows for bends and the motorcycle, maintains following gaps, and stops at red lights. Signals use simulated green/yellow/all-red cycles grouped around intersections; timings do not reproduce the county's actual signal plans. The scene maintains 44 nearby cars, recycling them outside the immediate riding area. Full intersection conflict resolution, protected turn phases and realistic lane changes remain unfinished. Detailed storefronts remain concentrated near Hall Road; the expanded area's building shells are less detailed.

## Township expansion and first-person pass

The map now follows Shelby Township’s official boundary and includes 13,227 mapped road sections, including 3,097 residential sections, plus the earlier 15–25 Mile corridor. Press **M** or click the mini-map to choose a road. Settings now offers helmet and cockpit cameras directly.

Road widths use mapped widths or lane counts when available. Fallbacks include Macomb County’s 28-foot subdivision cross section and separate freeway lanes and shoulders; these are design-standard estimates, not measurements of every existing road. Residential roofs, windows and driveways are reconstructed approximations. The 47,976 building records are not 47,976 individually surveyed, photorealistic buildings. 26,566 buildings currently have pitched-roof geometry. Some building types are inferred from footprint size and mapped residential land use.

Traffic observes signal phases, following distance, mapped turn restrictions and stop signs; curved turn paths and minor-road yielding are implemented. Traffic remains a simulation with limited vehicle variety and no full lane-changing model.

Reference sources:
- [Shelby Township GIS and zoning maps](https://www.shelbytwp.org/government/departments/planning-and-zoning/zoning-ordinance-maps)
- [Macomb County subdivision paving details](https://www.macombgov.org/sites/default/files/files/2025-04/Subdivision%20Paving%20Standard%20Details.pdf)
- [Shelby Township engineering standards](https://www.shelbytwp.org/home/showpublisheddocument/9010/638884418257770000)
- [Shops at Shelby Township site plan and facade reference](https://heidenbergproperties.com/wp-content/uploads/2018/12/Shelby-2018-brochure.pdf) (2018; current tenant names are not assumed)
- [Local ranch house reference](https://tours.proactive3dt.com/184091) (visual reference only; photograph not used as an in-game texture)

The world is an evolving reconstruction, not a verified one-to-one digital twin. Exact storefront elevations, individual house details, driveway locations, curb cuts and as-built road widths still need location-by-location verification.

Full regional footprint coverage was added from [SEMCOG Building Footprints](https://gis.semcog.org/server/rest/services/hosted/Building_Footprints/FeatureServer/14), current to April 2019. Building GLBs are streamed in 1 km sections around the rider and unloaded beyond 4 km. The building count includes the southern riding corridor and boundary buffer.
