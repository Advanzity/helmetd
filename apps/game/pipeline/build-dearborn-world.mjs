import {resolveFeaturedBusinesses} from '../src/featured-businesses.js';
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const output = fileURLToPath(new URL('../public/assets/dearborn-world.json', import.meta.url));
const runtimeOutput = fileURLToPath(new URL('../public/assets/compact-world.json', import.meta.url));
const parkingOutput = fileURLToPath(new URL('../public/assets/parking.json', import.meta.url));
const location = {name: 'Dearborn', county: 'Wayne County', lat: 42.3061, lon: -83.246};
const halfSize = 1800;
const drivableClasses=new Set(['motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','unclassified','residential','living_street','service']);
const metersPerDegree = 111320;
const longitudeScale = Math.cos(location.lat * Math.PI / 180);
const limits = [-halfSize, -halfSize, halfSize, halfSize];
const south = location.lat - halfSize / metersPerDegree;
const north = location.lat + halfSize / metersPerDegree;
const west = location.lon - halfSize / (metersPerDegree * longitudeScale);
const east = location.lon + halfSize / (metersPerDegree * longitudeScale);
const bbox = `${south},${west},${north},${east}`;
const query = `[out:json][timeout:120];(way["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|unclassified|residential|living_street|service)$"](${bbox});way["building"](${bbox});way["landuse"](${bbox});way["natural"~"^(water|wood|grass|wetland)$"](${bbox});way["waterway"](${bbox});way["amenity"="parking"](${bbox});node["highway"~"^(traffic_signals|stop)$"](${bbox});node["name"~"Qahwah|Jabal|Level Zero|Zero Smash",i](${bbox}););out body;>;out skel qt;`;
const endpoints = [
  'https://overpass.private.coffee/api/interpreter',
  'https://overpass.kumi.systems/api/interpreter',
  'https://overpass-api.de/api/interpreter',
];

function project(lon, lat) {
  return [(lon - location.lon) * metersPerDegree * longitudeScale,
    (lat - location.lat) * metersPerDegree];
}

function clipSegment(a, b) {
  let low = 0;
  let high = 1;
  for (let axis = 0; axis < 2; axis++) {
    const delta = b[axis] - a[axis];
    if (delta === 0) {
      if (Math.abs(a[axis]) > halfSize) return null;
      continue;
    }
    const ends = [(-halfSize - a[axis]) / delta, (halfSize - a[axis]) / delta].sort((x, y) => x - y);
    low = Math.max(low, ends[0]);
    high = Math.min(high, ends[1]);
  }
  return high > low ? [low, high] : null;
}

function measure(value) {
  if (!value) return null;
  const match = String(value).match(/[\d.]+/);
  if (!match) return null;
  const number = Number(match[0]);
  return /ft|feet/i.test(value) ? number * 0.3048 : number;
}

function roadWidth(tags) {
  const tagged = measure(tags.width);
  if (tagged) return tagged;
  const lanes = Math.max(1, Number.parseInt(tags.lanes, 10) || (tags.highway.includes('motorway') ? 4 : 2));
  const shoulder = tags.highway.includes('motorway') ? 5 : 1;
  return lanes * 3.35 + shoulder;
}

function clippedRoads(way, coordinates) {
  const roads = [];
  let run = null;
  const flush = () => {
    if (run && run.points.length >= 2) roads.push(run);
    run = null;
  };
  for (let i = 0; i < coordinates.length - 1; i++) {
    const a = coordinates[i];
    const b = coordinates[i + 1];
    const clipped = clipSegment(a, b);
    if (!clipped) {
      flush();
      continue;
    }
    const [low, high] = clipped;
    const pointAt = t => a.map((value, axis) => value + (b[axis] - value) * t);
    const pointA = pointAt(low);
    const pointB = pointAt(high);
    const idA = low === 0 ? String(way.nodes[i]) : `crop:${way.id}:${i}:in`;
    const idB = high === 1 ? String(way.nodes[i + 1]) : `crop:${way.id}:${i}:out`;
    if (!run || run.nodeIds.at(-1) !== idA) {
      flush();
      run = {points: [pointA], nodeIds: [idA]};
    }
    run.points.push(pointB);
    run.nodeIds.push(idB);
    if (high < 1) flush();
  }
  flush();

  const tags = way.tags || {};
  return roads.map(segment => {
    let points = segment.points;
    let nodeIds = segment.nodeIds;
    if (tags.oneway === '-1') {
      points = [...points].reverse();
      nodeIds = [...nodeIds].reverse();
    }
    const lanes = Math.max(1, Number.parseInt(tags.lanes, 10) || (tags.highway.includes('motorway') ? 4 : 2));
    return {
      id: String(way.id),
      name: tags.name || tags.ref || 'Local road',
      ref: tags.ref || '',
      class: tags.highway,
      lanes,
      laneWidth: 3.35,
      width: roadWidth(tags),
      shoulder: tags.highway.includes('motorway') ? 2.4 : 0.45,
      pavementOffset: 0,
      curb: ['residential', 'tertiary', 'secondary'].includes(tags.highway),
      oneway: tags.oneway === 'yes' || tags.oneway === '-1',
      bridge: tags.bridge === 'yes',
      surface: tags.surface === 'concrete' ? 'concrete' : 'asphalt',
      points,
      nodeIds,
    };
  });
}

function isClosed(way) {
  return way.nodes?.length >= 4 && way.nodes[0] === way.nodes.at(-1);
}

function polygonCoordinates(way, nodes) {
  const points = way.nodes.map(id => nodes.get(String(id))).filter(Boolean).map(node => project(node.lon, node.lat));
  if (points.length < 4 || points.some(([x, y]) => Math.abs(x) > halfSize || Math.abs(y) > halfSize)) return null;
  return points;
}

function polygonArea(points) {
  return Math.abs(points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point[0] * next[1] - next[0] * point[1];
  }, 0)) / 2;
}

async function fetchMap() {
  const errors = [];
  for (const endpoint of endpoints) {
    try {
      console.log(`Querying ${endpoint}...`);
      const url = `${endpoint}?data=${encodeURIComponent(query)}`;
      const response = await fetch(url, {
        headers: {'User-Agent': 'Helmetd-Dearborn-world-builder/1.0 (local development)'},
        signal: AbortSignal.timeout(30000),
      });
      console.log(`OSM endpoint returned HTTP ${response.status}.`);
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${(await response.text()).slice(0, 160)}`);
      return await response.json();
    } catch (error) {
      errors.push(`${endpoint}: ${error.message}`);
    }
  }
  throw new Error(`All OSM endpoints failed. ${errors.join(' | ')}`);
}

console.log(`Fetching OSM features around Michigan Avenue, ${location.name}...`);
const inputIndex=process.argv.indexOf('--input');
const osm=inputIndex>=0?JSON.parse(await readFile(process.argv[inputIndex+1],'utf8')):await fetchMap();
if (!osm.elements) throw new Error(osm.remark || 'OSM response did not include elements');
const nodes = new Map(osm.elements.filter(item => item.type === 'node').map(node => [String(node.id), node]));
const roads = [];
const buildings = [];
const land = [];
const parking = [];
const signals = [];
const stops = [];

for (const element of osm.elements) {
  if (element.type === 'node') {
    const point = project(element.lon, element.lat);
    if (element.tags?.highway === 'traffic_signals') signals.push({node: String(element.id), kind: 'traffic_signals', point});
    if (element.tags?.highway === 'stop') stops.push({node: String(element.id), kind: 'stop', point});
    continue;
  }
  if (element.type !== 'way' || !element.nodes?.length) continue;
  const tags = element.tags || {};
  const coordinates = element.nodes.map(id => nodes.get(String(id))).filter(Boolean).map(node => [...project(node.lon, node.lat), 0]);
  if (drivableClasses.has(tags.highway) && coordinates.length >= 2) roads.push(...clippedRoads(element, coordinates));
  if (!isClosed(element)) continue;
  const points = polygonCoordinates(element, nodes);
  if (!points) continue;
  if (tags.building) {
    const levels = Number.parseFloat(tags['building:levels']) || 0;
    const height = Math.max(3, Math.min(60, measure(tags.height) || (levels ? levels * 3 : (tags.building === 'house' || tags.building === 'residential' ? 6 : 10))));
    buildings.push({id: String(element.id), points, height, base: 0, type: tags.building, name: tags.name, amenity: tags.amenity, shop: tags.shop, heightTagged: Boolean(tags.height || levels)});
  }
  const landType = tags.landuse || tags.natural || (tags.waterway ? 'water' : null);
  if (landType) {
    const normalized = landType === 'forest' || landType === 'wood' ? 'wood' :
      ['water', 'riverbank', 'wetland'].includes(landType) || tags.waterway ? 'water' : landType;
    if (['grass', 'wood', 'forest', 'meadow', 'water', 'river'].includes(normalized)) land.push({type: normalized, points});
  }
  if (tags.amenity === 'parking' && polygonArea(points) > 80) {
    parking.push({points, area: polygonArea(points)});
  }
}

if (!roads.some(road => road.name === 'Michigan Avenue')) {
  throw new Error('The selected map extract does not include Michigan Avenue.');
}
const resolution = 121;
const roadNodes=new Set(roads.flatMap(road=>road.nodeIds));
const freewayName = roads.find(road => road.class === 'motorway')?.name || 'Michigan Avenue';
const world = {
  locationName: location.name,
  regionName: location.county,
  districtName: 'West Dearborn',
  primaryRoadName: 'Michigan Avenue',
  primaryRoadRef: 'US 12',
  freewayName,
  mapLabels: ['Michigan Avenue', 'Warren Avenue', 'Mason Street', 'Monroe Street', 'Military Street', 'Telegraph Road', 'Outer Drive'],
  origin: [location.lon, location.lat],
  baseElevation: 0,
  size: halfSize * 2,
  resolution,
  heights: Array(resolution * resolution).fill(0),
  roads,
  buildings,
  businesses: resolveFeaturedBusinesses(osm,[location.lon,location.lat]),
  land,
  parking,
  signals: signals.filter(signal=>roadNodes.has(signal.node)),
  stops: stops.filter(stop=>roadNodes.has(stop.node)),
  restrictions: [],
  turningCircles: [],
  bounds: limits,
  townshipBoundary: [[-halfSize, -halfSize], [halfSize, -halfSize], [halfSize, halfSize], [-halfSize, halfSize], [-halfSize, -halfSize]],
  buildingTiles: [],
  simpleBuildings: true,
  aerialTexture: false,
  frontages: false,
  coverage: '3.6 km West Dearborn riding area centered on Michigan Avenue and Mason Street',
  sources: ['OpenStreetMap contributors, ODbL 1.0'],
};

const serialized = JSON.stringify(world);
await Promise.all([writeFile(output, serialized), writeFile(runtimeOutput, serialized), writeFile(parkingOutput, JSON.stringify(parking))]);
console.log(`Saved ${path.relative(process.cwd(), output)}: ${roads.length} road segments, ${buildings.length} buildings, ${land.length} land polygons, ${world.signals.length} signals.`);
