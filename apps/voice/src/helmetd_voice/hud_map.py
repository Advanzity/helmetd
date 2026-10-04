"""Bounded north-up route geometry for the native HUD; no tile credentials or GPS logs."""
import math


def map_command(data):
    route = data.get('route') or data.get('preview')
    if not route or len(route.get('geometry', [])) < 2:
        return 'nav_map none -1 -1 0'
    geometry = route['geometry']
    origin = geometry[0]
    scale = math.cos(math.radians(origin[0]))

    def project(point):
        return (((point[1] - origin[1] + 180) % 360 - 180) * scale,
                origin[0] - point[0])

    points = [project(point) for point in geometry]
    low = [min(p[i] for p in points) for i in (0, 1)]
    high = [max(p[i] for p in points) for i in (0, 1)]
    # Match the native plot's 276:156 aspect ratio without stretching the route.
    span = max(high[0] - low[0], (high[1] - low[1]) * 276 / 156, 0.0001)
    cx, cy = [(low[i] + high[i]) / 2 for i in (0, 1)]

    def normalize(point):
        return (round(500 + (point[0] - cx) * 1000 / span),
                round(500 + (point[1] - cy) * 1000 / (span * 156 / 276)))

    points = [normalize(point) for point in points]
    # Douglas-Peucker simplification preserves bends instead of sampling by index.
    def simplify(tolerance):
        keep = {0, len(points) - 1}
        stack = [(0, len(points) - 1)]
        while stack:
            start, end = stack.pop()
            ax, ay = points[start]
            dx, dy = points[end][0] - ax, points[end][1] - ay
            squared = dx * dx + dy * dy
            best, index = tolerance * tolerance, None
            for i in range(start + 1, end):
                x, y = points[i][0] - ax, points[i][1] - ay
                ratio = max(0, min(1, (x * dx + y * dy) / squared)) if squared else 0
                distance = (x - ratio * dx) ** 2 + (y - ratio * dy) ** 2
                if distance > best:
                    best, index = distance, i
            if index is not None:
                keep.add(index)
                stack.extend(((start, index), (index, end)))
        return [points[i] for i in sorted(keep)]

    tolerance = 1
    simplified = simplify(tolerance)
    while len(simplified) > 32:
        tolerance *= 2
        simplified = simplify(tolerance)
    fix = data.get('fix')
    x = y = -1
    if fix and fix.get('guidance_usable'):
        x, y = normalize(project(fix['point']))
        if not (0 <= x <= 1000 and 0 <= y <= 1000):
            x = y = -1
    mode = 'preview' if not data.get('route') else 'active'
    if mode == 'active' and (not fix or not fix.get('guidance_usable')):
        mode = 'stale'
    values = ' '.join(f'{x} {y}' for x, y in simplified)
    return f'nav_map {mode} {x} {y} {len(simplified)} {values}'
