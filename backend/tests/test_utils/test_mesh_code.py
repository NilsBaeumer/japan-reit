"""Tests for JIS mesh code utilities."""

from app.utils.mesh_code import latlng_to_mesh, mesh_to_bounds, mesh_center


class TestLatlngToMesh:
    def test_tokyo_station_level3(self):
        # Tokyo Station: lat=35.6812, lng=139.7671
        mesh = latlng_to_mesh(35.6812, 139.7671, level=3)
        assert len(mesh) == 8
        assert mesh.startswith("5339")  # Tokyo area 1st mesh

    def test_osaka_level2(self):
        # Osaka: lat=34.6937, lng=135.5023
        mesh = latlng_to_mesh(34.6937, 135.5023, level=2)
        assert len(mesh) == 6

    def test_level1(self):
        mesh = latlng_to_mesh(35.6812, 139.7671, level=1)
        assert len(mesh) == 4


class TestMeshToBounds:
    def test_roundtrip(self):
        lat, lng = 35.6812, 139.7671
        mesh = latlng_to_mesh(lat, lng, level=3)
        bounds = mesh_to_bounds(mesh)

        # Original point should be within bounds
        assert bounds["south"] <= lat <= bounds["north"]
        assert bounds["west"] <= lng <= bounds["east"]

    def test_mesh_center(self):
        mesh = latlng_to_mesh(35.6812, 139.7671, level=3)
        center_lat, center_lng = mesh_center(mesh)

        # Center should be roughly near Tokyo
        assert 35.0 < center_lat < 36.0
        assert 139.0 < center_lng < 140.0
