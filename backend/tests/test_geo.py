"""Unit tests for geospatial helpers (#7/#8/#9), pure functions, no DB."""
from __future__ import annotations

import pytest

from app.services import geo


def test_extract_coords_variants():
    assert geo.extract_coords({"latitude": 9.03, "longitude": 38.74}) == geo.Coords(9.03, 38.74)
    assert geo.extract_coords({"lat": 1.0, "lng": 2.0}) == geo.Coords(1.0, 2.0)
    assert geo.extract_coords({"coordinates": [51.5, -0.12]}) == geo.Coords(51.5, -0.12)


def test_extract_coords_rejects_out_of_range_and_missing():
    assert geo.extract_coords({"latitude": 200, "longitude": 0}) is None
    assert geo.extract_coords({"latitude": "x", "longitude": "y"}) is None
    assert geo.extract_coords({}) is None
    assert geo.extract_coords(None) is None


def test_haversine_known_distance():
    # London ↔ Paris ≈ 343 km
    london = geo.Coords(51.5074, -0.1278)
    paris = geo.Coords(48.8566, 2.3522)
    assert geo.haversine_km(london, paris) == pytest.approx(343, abs=5)


def test_haversine_zero():
    p = geo.Coords(10.0, 20.0)
    assert geo.haversine_km(p, p) == 0.0
