"""Yen formatting and conversion utilities."""


def format_yen(amount: int | float) -> str:
    """Format amount in yen with comma separators. e.g. 1500000 -> '¥1,500,000'"""
    return f"¥{int(amount):,}"


def format_man_yen(amount: int | float) -> str:
    """Format amount in 万円 (10,000 yen units). e.g. 1500000 -> '150万円'"""
    man = amount / 10_000
    if man == int(man):
        return f"{int(man)}万円"
    return f"{man:.1f}万円"


def yen_to_man(amount: int | float) -> float:
    """Convert yen to 万円 units."""
    return amount / 10_000


def man_to_yen(amount: float) -> int:
    """Convert 万円 to yen."""
    return int(amount * 10_000)


def sqm_to_tsubo(sqm: float) -> float:
    """Convert square meters to tsubo (坪). 1 tsubo ≈ 3.306 sqm."""
    return round(sqm / 3.30579, 2)


def tsubo_to_sqm(tsubo: float) -> float:
    """Convert tsubo to square meters."""
    return round(tsubo * 3.30579, 2)


def price_per_tsubo(price: int, area_sqm: float) -> int:
    """Calculate price per tsubo."""
    if area_sqm <= 0:
        return 0
    tsubo = sqm_to_tsubo(area_sqm)
    return int(price / tsubo) if tsubo > 0 else 0
