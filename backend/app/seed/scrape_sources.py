"""Default scraping source configurations."""

SCRAPE_SOURCES = [
    {
        "id": "suumo",
        "display_name": "SUUMO (スーモ)",
        "base_url": "https://suumo.jp/",
        "is_enabled": True,
        "default_interval_hours": 24,
        "config": {
            "search_type": "中古戸建",
            "crawl_delay_seconds": 30,
            "max_pages_per_run": 50,
        },
    },
    {
        "id": "homes",
        "display_name": "LIFULL HOME'S",
        "base_url": "https://www.homes.co.jp/",
        "is_enabled": True,
        "default_interval_hours": 24,
        "config": {
            "crawl_delay_seconds": 15,
            "max_pages_per_run": 50,
        },
    },
    {
        "id": "athome",
        "display_name": "at home (アットホーム)",
        "base_url": "https://www.athome.co.jp/",
        "is_enabled": True,
        "default_interval_hours": 48,
        "config": {
            "crawl_delay_seconds": 15,
            "max_pages_per_run": 30,
        },
    },
    {
        "id": "akiya",
        "display_name": "Akiya Banks (空き家バンク)",
        "base_url": None,
        "is_enabled": True,
        "default_interval_hours": 168,  # Weekly
        "config": {
            "crawl_delay_seconds": 5,
            "municipalities": [],
        },
    },
    {
        "id": "bit",
        "display_name": "BIT Court Auctions (裁判所競売)",
        "base_url": "https://www.bit.courts.go.jp/",
        "is_enabled": True,
        "default_interval_hours": 72,
        "config": {
            "crawl_delay_seconds": 10,
            "max_pages_per_run": 20,
        },
    },
]
