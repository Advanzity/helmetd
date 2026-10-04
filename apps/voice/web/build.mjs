import {copyFile, mkdir, readFile, writeFile, rename} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';

// Download the vendor's pinned, self-contained npm browser bundle once.
// No package installation or external scripts are needed at runtime.
const url = 'https://cdn.jsdelivr.net/npm/@elevenlabs/client@1.26.0/dist/lib.iife.js';
const expected = '7737528b7dddb223a58755333ce2e7102cbf8edde6e9c68adb3828e602688a7b';
const digest = data => createHash('sha256').update(data).digest('hex');
const vendor = 'dist/elevenlabs.js';
await mkdir('dist', {recursive: true});
let data;
try { data = await readFile(vendor); } catch { /* First build. */ }
if (!data || digest(data) !== expected) {
  const response = await fetch(url, {signal: AbortSignal.timeout(120000)});
  if (!response.ok) throw new Error(`SDK download failed (${response.status}).`);
  data = Buffer.from(await response.arrayBuffer());
  if (digest(data) !== expected) throw new Error('SDK checksum did not match the pinned release.');
  await writeFile(`${vendor}.tmp.js`, data);
  execFileSync(process.execPath, ['--check', `${vendor}.tmp.js`]);
  await rename(`${vendor}.tmp.js`, vendor);
}
execFileSync(process.execPath, ['--check', 'client.js']);
await copyFile('client.js', 'dist/client.js');
execFileSync(process.execPath, ['--check', 'navigation.js']);
await copyFile('navigation.js', 'dist/navigation.js');
await copyFile('navigation.css', 'dist/navigation.css');
// Hashes published by https://leafletjs.com/download.html for Leaflet 1.9.4.
for (const [name, sha256] of [
  ['leaflet.js', '20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo='],
  ['leaflet.css', 'p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY='],
]) {
  const file = `dist/${name}`;
  let bytes;
  try { bytes = await readFile(file); } catch { /* First build. */ }
  const matches = value => value && createHash('sha256').update(value).digest('base64') === sha256;
  if (!matches(bytes)) {
    const response = await fetch(`https://unpkg.com/leaflet@1.9.4/dist/${name}`, {signal: AbortSignal.timeout(30000)});
    if (!response.ok) throw new Error(`Leaflet download failed (${response.status}).`);
    bytes = Buffer.from(await response.arrayBuffer());
    if (!matches(bytes)) throw new Error('Leaflet checksum mismatch.');
    await writeFile(file, bytes);
  }
}
await copyFile('leaflet-LICENSE.txt', 'dist/leaflet-LICENSE.txt');
// Files extracted from the registry-integrity-verified MapLibre release.
const maplibre = JSON.parse(await readFile('maplibre-vendor.json', 'utf8'));
for (const [name, checksum] of Object.entries(maplibre.sha256)) {
  const path = `dist/${name}`;
  let bytes;
  try { bytes = await readFile(path); } catch { /* First build. */ }
  if (!bytes || digest(bytes) !== checksum) {
    const response = await fetch(`https://unpkg.com/maplibre-gl@${maplibre.version}/dist/${name}`, {signal: AbortSignal.timeout(30000)});
    if (!response.ok) throw new Error(`MapLibre download failed (${response.status}).`);
    bytes = Buffer.from(await response.arrayBuffer());
    if (digest(bytes) !== checksum) throw new Error('MapLibre checksum mismatch.');
    await writeFile(path, bytes);
  }
}
await copyFile('maplibre-LICENSE.txt', 'dist/maplibre-LICENSE.txt');
execFileSync(process.execPath, ['--check', 'earth-map.js']);
await copyFile('earth-map.js', 'dist/earth-map.js');
execFileSync(process.execPath, ['--check', 'ride-audio.js']);
await copyFile('ride-audio.js', 'dist/ride-audio.js');
execFileSync(process.execPath, ['--check', 'nearby.js']);
await copyFile('nearby.js', 'dist/nearby.js');
await copyFile('nearby.css', 'dist/nearby.css');
execFileSync(process.execPath, ['--check', 'helmet-controls.js']);
await copyFile('helmet-controls.js', 'dist/helmet-controls.js');
console.log('Built Helmetd nearby console; pinned vendor checksums verified.');

execFileSync(process.execPath, ['--check', 'local-api.js']);
await copyFile('local-api.js', 'dist/local-api.js');

await copyFile('hud-map.html', 'dist/hud-map.html');

execFileSync(process.execPath, ['--check', 'helmet-audio.js']);
await copyFile('helmet-audio.js', 'dist/helmet-audio.js');

await copyFile('../../../docs/design/hud/assets/utility-icons-white-v1.png', 'dist/utility-icons-white-v1.png');
await copyFile('../../../docs/design/hud/assets/notification-white-v1.png', 'dist/notification-white-v1.png');

execFileSync(process.execPath, ['--check', 'road-reports.js']);
await copyFile('road-reports.js', 'dist/road-reports.js');

await copyFile('../../../docs/design/hud/assets/road-warnings-v1.png', 'dist/road-warnings-v1.png');
