"""Japanese era (和暦) to Western year conversion utilities."""

import re

# Era start years
ERAS = {
    "令和": 2018,  # Reiwa: 2019 = Reiwa 1
    "平成": 1988,  # Heisei: 1989 = Heisei 1
    "昭和": 1925,  # Showa: 1926 = Showa 1
    "大正": 1911,  # Taisho: 1912 = Taisho 1
    "明治": 1867,  # Meiji: 1868 = Meiji 1
}

ERA_PATTERN = re.compile(r"(令和|平成|昭和|大正|明治)(\d+)年?")


def japanese_era_to_western(era_str: str) -> int | None:
    """
    Convert Japanese era year to Western year.

    Examples:
        "令和6年" -> 2024
        "平成30年" -> 2018
        "昭和50年" -> 1975
    """
    match = ERA_PATTERN.search(era_str)
    if not match:
        return None

    era_name = match.group(1)
    era_year = int(match.group(2))

    base = ERAS.get(era_name)
    if base is None:
        return None

    return base + era_year


def western_to_japanese_era(year: int) -> str:
    """
    Convert Western year to Japanese era string.

    Examples:
        2024 -> "令和6年"
        2018 -> "平成30年"
    """
    if year >= 2019:
        return f"令和{year - 2018}年"
    elif year >= 1989:
        return f"平成{year - 1988}年"
    elif year >= 1926:
        return f"昭和{year - 1925}年"
    elif year >= 1912:
        return f"大正{year - 1911}年"
    elif year >= 1868:
        return f"明治{year - 1867}年"
    else:
        return f"{year}年"


def building_age_years(year_built: int | None, reference_year: int = 2026) -> int | None:
    """Calculate building age in years."""
    if year_built is None:
        return None
    return max(0, reference_year - year_built)


def tax_depreciation_remaining(
    year_built: int,
    structure: str = "wood",
    reference_year: int = 2026,
) -> int:
    """
    Calculate remaining tax depreciation years.

    Statutory useful life (法定耐用年数):
    - Wood residential: 22 years
    - Steel frame: 34 years
    - RC residential: 47 years
    - SRC residential: 47 years
    """
    useful_life = {
        "wood": 22,
        "steel_frame": 34,
        "rc": 47,
        "src": 47,
        "light_steel": 27,
    }

    life = useful_life.get(structure, 22)
    age = reference_year - year_built
    remaining = max(0, life - age)
    return remaining
