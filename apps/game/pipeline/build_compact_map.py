"""Build the smaller playable map without modifying the full geographic source."""
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'public' / 'assets'
LIMIT = 1800


def inside(p):
    return all(-LIMIT <= p[i] <= LIMIT for i in range(2))


def clip_segment(a, b):
    lo, hi = 0, 1
    for i in range(2):
        delta = b[i] - a[i]
        if delta == 0:
            if abs(a[i]) > LIMIT:
                return None
            continue
        ends = sorted(((-LIMIT - a[i]) / delta, (LIMIT - a[i]) / delta))
        lo, hi = max(lo, ends[0]), min(hi, ends[1])
    if hi <= lo:
        return None
    return lo, hi


def build(data):
    roads = []
    for road in data['roads']:
        run = None
        for i, (a, b) in enumerate(zip(road['points'], road['points'][1:])):
            clipped = clip_segment(a, b)
            if clipped is None:
                run = None
                continue
            lo, hi = clipped
            points = [[a[k] + (b[k] - a[k]) * t for k in range(3)] for t in (lo, hi)]
            ids = [road['nodeIds'][i] if lo == 0 else f"crop:{road['id']}:{i}:in",
                   road['nodeIds'][i + 1] if hi == 1 else f"crop:{road['id']}:{i}:out"]
            if run is not None and run['nodeIds'][-1] == ids[0]:
                run['points'].append(points[1])
                run['nodeIds'].append(ids[1])
            else:
                run = {**road, 'points': points, 'nodeIds': ids}
                roads.append(run)
            if hi < 1:
                run = None
    nodes = {node for road in roads for node in road['nodeIds']}
    result = {**data, 'roads': roads, 'bounds': [-LIMIT, -LIMIT, LIMIT, LIMIT],
              'coverage': 'Compact Hall Road / M-53 riding area',
              'townshipBoundary': [[-LIMIT, -LIMIT], [LIMIT, -LIMIT], [LIMIT, LIMIT],
                                   [-LIMIT, LIMIT], [-LIMIT, -LIMIT]]}
    result.pop('outerTerrain', None)
    result.pop('townshipAreaSquareMiles', None)
    for name in ('buildings', 'land'):
        result[name] = [item for item in data[name] if all(inside(p) for p in item['points'])]
    for name in ('signals', 'stops'):
        result[name] = [item for item in data.get(name, []) if item['node'] in nodes]
    result['turningCircles'] = [item for item in data.get('turningCircles', [])
                                if all(abs(v) + item['radius'] <= LIMIT for v in item['point'][:2])]
    result['restrictions'] = [item for item in data.get('restrictions', []) if item['via'] in nodes]
    return result


if __name__ == '__main__':
    original = json.loads((ASSETS / 'world.json').read_text(encoding='utf-8'))
    compact = build(original)
    (ASSETS / 'compact-world.json').write_text(json.dumps(compact, separators=(',', ':')), encoding='utf-8')
    for name in ('roads', 'buildings', 'land'):
        print(f"{name}: {len(original[name])} -> {len(compact[name])}")
