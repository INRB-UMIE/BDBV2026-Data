from tools import build_geojson


def test_round_coords_rounds_point():
    assert build_geojson._round_coords([1.123456789, -2.987654321]) == [1.12346, -2.98765]


def test_round_coords_rounds_nested_polygon_rings():
    # Polygon: list of rings, each ring a list of [x, y] pairs.
    coords = [
        [[1.111111, 2.222222], [3.333333, 4.444444], [1.111111, 2.222222]],
    ]
    rounded = build_geojson._round_coords(coords)
    assert rounded == [
        [[1.11111, 2.22222], [3.33333, 4.44444], [1.11111, 2.22222]],
    ]


def test_round_coords_handles_empty():
    assert build_geojson._round_coords([]) == []


def test_simplify_geometry_reduces_vertex_count_and_rounds():
    # A near-degenerate "staircase" ring: many collinear-ish points along each
    # edge that a simplify pass at SIMPLIFY_TOL should collapse away, similar
    # in spirit to a shapefile with far more vertex density than the polygon's
    # actual shape needs.
    ring = [[0.0, 0.0]]
    for i in range(1, 50):
        ring.append([i * 0.0001, 0.0000001 * (i % 2)])
    ring.append([5.0, 5.0])
    ring.append([0.0, 5.0])
    ring.append([0.0, 0.0])

    geo_interface = {"type": "Polygon", "coordinates": [ring]}
    result = build_geojson._simplify_geometry(geo_interface)

    assert result["type"] == "Polygon"
    before_count = len(ring)
    after_count = len(result["coordinates"][0])
    assert after_count < before_count

    # Coordinates should be rounded to COORD_DECIMALS.
    for x, y in result["coordinates"][0]:
        assert round(x, build_geojson.COORD_DECIMALS) == x
        assert round(y, build_geojson.COORD_DECIMALS) == y


def test_simplify_geometry_never_drops_feature():
    # A tiny, simple triangle well under SIMPLIFY_TOL in every dimension.
    # Simplification must never leave a feature with empty geometry — fall
    # back to the (rounded) original instead.
    tiny = [[0.0, 0.0], [0.0002, 0.0], [0.0001, 0.0002], [0.0, 0.0]]
    geo_interface = {"type": "Polygon", "coordinates": [tiny]}
    result = build_geojson._simplify_geometry(geo_interface)

    assert result["type"] == "Polygon"
    assert len(result["coordinates"][0]) >= 3
