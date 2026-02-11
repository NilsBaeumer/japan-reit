"""
JIS standard mesh code (JIS X 0410) conversion utilities.

Mesh hierarchy:
- 1st mesh (~80km): 4 digits
- 2nd mesh (~10km): 6 digits
- 3rd mesh (~1km): 8 digits
- Half mesh (~500m): 9 digits
- Quarter mesh (~250m): 10 digits

Used by J-SHIS API and reinfolib population mesh data.
"""

import math


def latlng_to_mesh(lat: float, lng: float, level: int = 3) -> str:
    """
    Convert latitude/longitude to JIS mesh code.

    Args:
        lat: Latitude in degrees (WGS84)
        lng: Longitude in degrees (WGS84)
        level: Mesh level (1, 2, 3, or 4 for half-mesh)

    Returns:
        Mesh code string
    """
    # 1st mesh (primary area partition)
    lat_rem = lat * 60  # Convert to minutes
    p = int(lat_rem / 40)
    lat_rem -= p * 40

    u = int(lng - 100)
    lng_rem = lng - 100 - u

    code = f"{p:02d}{u:02d}"
    if level == 1:
        return code

    # 2nd mesh
    q = int(lat_rem / 5)
    lat_rem -= q * 5

    v = int(lng_rem * 60 / 7.5)
    lng_rem -= v * 7.5 / 60

    code += f"{q}{v}"
    if level == 2:
        return code

    # 3rd mesh (standard area mesh, ~1km)
    r = int(lat_rem * 60 / 30)
    lat_rem_sec = lat_rem * 60 - r * 30

    w = int(lng_rem * 3600 / 45)
    lng_rem_sec = lng_rem * 3600 - w * 45

    code += f"{r}{w}"
    if level == 3:
        return code

    # Half mesh (~500m)
    half_lat = 0 if lat_rem_sec < 15 else 1
    half_lng = 0 if lng_rem_sec < 22.5 else 1
    half = half_lat * 2 + half_lng + 1

    code += f"{half}"
    return code


def mesh_to_bounds(mesh_code: str) -> dict:
    """
    Convert mesh code to bounding box coordinates.

    Returns:
        dict with 'south', 'north', 'west', 'east' in degrees
    """
    code = str(mesh_code)
    level = len(code)

    if level < 4:
        raise ValueError(f"Invalid mesh code: {code}")

    # 1st mesh
    p = int(code[0:2])
    u = int(code[2:4])

    south = p * 40 / 60
    north = south + 40 / 60
    west = u + 100
    east = west + 1

    if level >= 6:
        # 2nd mesh
        q = int(code[4])
        v = int(code[5])
        south = south + q * 5 / 60
        north = south + 5 / 60
        west = west + v * 7.5 / 60
        east = west + 7.5 / 60

    if level >= 8:
        # 3rd mesh
        r = int(code[6])
        w = int(code[7])
        south = south + r * 30 / 3600
        north = south + 30 / 3600
        west = west + w * 45 / 3600
        east = west + 45 / 3600

    if level >= 9:
        # Half mesh
        half = int(code[8]) - 1
        half_lat = half // 2
        half_lng = half % 2
        height = (north - south) / 2
        width = (east - west) / 2
        south = south + half_lat * height
        north = south + height
        west = west + half_lng * width
        east = west + width

    return {
        "south": south,
        "north": north,
        "west": west,
        "east": east,
    }


def mesh_center(mesh_code: str) -> tuple[float, float]:
    """Get center lat/lng of a mesh code."""
    bounds = mesh_to_bounds(mesh_code)
    lat = (bounds["south"] + bounds["north"]) / 2
    lng = (bounds["west"] + bounds["east"]) / 2
    return (lat, lng)
