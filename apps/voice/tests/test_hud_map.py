from helmetd_voice.hud_map import map_command


def decode(data):
    _, mode, x, y, count, *values = map_command(data).split()
    points = list(zip(map(int, values[::2]), map(int, values[1::2])))
    assert len(points) == int(count) <= 32
    assert all(0 <= v <= 1000 for point in points for v in point)
    return mode, (int(x), int(y)), points


def test_route_bends_position_and_preview():
    route = {'geometry': [[42, -83], [42.01, -83], [42.01, -82.99]]}
    mode, marker, points = decode({'preview': route})
    assert mode == 'preview' and marker == (-1, -1) and len(points) == 3
    assert points[0][1] > points[1][1] and points[1][0] < points[2][0]
    mode, marker, points = decode({'route': route, 'fix': {'point': [42, -83], 'guidance_usable': True}})
    assert mode == 'active' and marker == points[0]
    assert decode({'route': route})[:2] == ('stale', (-1, -1))
    assert map_command({}) == 'nav_map none -1 -1 0'


def test_large_route_is_bounded_and_keeps_endpoints():
    import math
    route = {'geometry': [[42+i*.0001, -83+math.sin(i)*.001] for i in range(3000)]}
    command = map_command({'route': route})
    assert len(command) < 900
    _, _, points = decode({'route': route})
    assert points[0][1] > points[-1][1]
