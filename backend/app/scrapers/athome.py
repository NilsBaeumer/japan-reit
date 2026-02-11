"""
at home (athome.co.jp) scraper for used detached houses (中古一戸建て).

at home is one of Japan's major real estate portals. This scraper:
1. Navigates the 中古一戸建て search with price/area filters
2. Paginates through search results
3. Extracts listing data from search result cards
4. Scrapes detail pages for additional data (road, zoning, etc.)

Uses Playwright for JS-rendered content.
Crawl delay: 5s between pages (respecting server load).
"""

import re

import structlog
from bs4 import BeautifulSoup, Tag

from app.scrapers.base import AbstractScraper, RawListing, SearchParams
from app.scrapers.registry import register_scraper

logger = structlog.get_logger()

# Map JIS prefecture codes to at home URL slugs
PREFECTURE_NAMES: dict[str, str] = {
    "01": "hokkaido",
    "02": "aomori",
    "03": "iwate",
    "04": "miyagi",
    "05": "akita",
    "06": "yamagata",
    "07": "fukushima",
    "08": "ibaraki",
    "09": "tochigi",
    "10": "gunma",
    "11": "saitama",
    "12": "chiba",
    "13": "tokyo",
    "14": "kanagawa",
    "15": "niigata",
    "16": "toyama",
    "17": "ishikawa",
    "18": "fukui",
    "19": "yamanashi",
    "20": "nagano",
    "21": "gifu",
    "22": "shizuoka",
    "23": "aichi",
    "24": "mie",
    "25": "shiga",
    "26": "kyoto",
    "27": "osaka",
    "28": "hyogo",
    "29": "nara",
    "30": "wakayama",
    "31": "tottori",
    "32": "shimane",
    "33": "okayama",
    "34": "hiroshima",
    "35": "yamaguchi",
    "36": "tokushima",
    "37": "kagawa",
    "38": "ehime",
    "39": "kochi",
    "40": "fukuoka",
    "41": "saga",
    "42": "nagasaki",
    "43": "kumamoto",
    "44": "oita",
    "45": "miyazaki",
    "46": "kagoshima",
    "47": "okinawa",
}


@register_scraper("athome")
class AtHomeScraper(AbstractScraper):
    """Scraper for at home (athome.co.jp) 中古一戸建て (used detached houses)."""

    source_id = "athome"
    base_url = "https://www.athome.co.jp"
    crawl_delay_seconds = 5.0

    def _build_search_url(self, params: SearchParams, page: int = 1) -> str:
        """
        Build at home search URL for used detached houses.

        URL pattern:
          https://www.athome.co.jp/kodate/chuko/{prefecture_name}/list/
        Query parameters:
          price_to  = price ceiling in 万円
          page      = page number
        """
        prefecture_code = params.prefecture_code or "13"
        prefecture_name = PREFECTURE_NAMES.get(prefecture_code, "tokyo")
        price_man = params.price_max // 10_000

        url = (
            f"{self.base_url}/kodate/chuko/{prefecture_name}/list/"
            f"?price_to={price_man}&page={page}"
        )

        if params.price_min is not None:
            price_min_man = params.price_min // 10_000
            url += f"&price_from={price_min_man}"

        return url

    async def search_listings(self, params: SearchParams) -> list[RawListing]:
        """Search at home for 中古一戸建て listings matching criteria."""
        from playwright.async_api import async_playwright

        listings: list[RawListing] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ja-JP",
            )
            pw_page = await context.new_page()

            try:
                for page_num in range(1, params.max_pages + 1):
                    url = self._build_search_url(params, page_num)
                    logger.info("Scraping at home page", page=page_num, url=url)

                    await pw_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await pw_page.wait_for_timeout(3000)

                    html = await pw_page.content()
                    page_listings = self._parse_search_results(html)

                    if not page_listings:
                        logger.info("No more results", page=page_num)
                        break

                    listings.extend(page_listings)
                    logger.info(
                        "Parsed at home page",
                        page=page_num,
                        count=len(page_listings),
                        total=len(listings),
                    )

                    # Check if there's a next page
                    if not self._has_next_page(html):
                        logger.info("Reached last page", page=page_num)
                        break

                    await self._delay()

            except Exception as e:
                logger.error("at home search failed", error=str(e))
                raise
            finally:
                await browser.close()

        return listings

    def _has_next_page(self, html: str) -> bool:
        """Check if there are more pages of results."""
        soup = BeautifulSoup(html, "lxml")
        # at home pagination: look for "次へ" (next) link or next-page arrow
        next_link = soup.select_one(
            "a:contains('次へ'), "
            "a[rel='next'], "
            ".pagination a.next, "
            ".paginate a.next, "
            "[class*='pager'] a.next, "
            "[class*='pagination'] a:last-child"
        )
        if next_link:
            return True
        # Also check numbered pagination links
        pagination = soup.select(
            ".pagination li, .paginate li, "
            "[class*='pager'] a, [class*='pagination'] a"
        )
        return len(pagination) > 1

    def _parse_search_results(self, html: str) -> list[RawListing]:
        """Parse at home search results page HTML."""
        soup = BeautifulSoup(html, "lxml")
        listings: list[RawListing] = []

        # at home uses various card/table containers for listing results
        # Try multiple selectors for different page layouts
        property_cards = (
            soup.select("[class*='property-card']")
            or soup.select("[class*='propertyCard']")
            or soup.select("[class*='kodate-card']")
            or soup.select("[class*='estate-card']")
            or soup.select(".p-property-object")
            or soup.select("[class*='object-card']")
            or soup.select("[class*='bukken']")
            or soup.select("article[class*='property']")
            or soup.select("[data-property-id]")
        )

        if not property_cards:
            # Fallback: find any block containing property detail links
            property_cards = []
            for link in soup.select(
                "a[href*='/kodate/'], "
                "a[href*='/chuko/'], "
                "a[href*='/home/']"
            ):
                href = link.get("href", "")
                if isinstance(href, list):
                    href = href[0]
                # Filter to links that look like detail pages (contain numeric IDs)
                if re.search(r"/\d{5,}/", href):
                    parent = link.find_parent(["div", "li", "tr", "article", "section"])
                    if parent and parent not in property_cards:
                        property_cards.append(parent)

        for card in property_cards:
            try:
                listing = self._parse_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.warning("Failed to parse at home card", error=str(e))

        return listings

    def _parse_card(self, card: Tag) -> RawListing | None:
        """Parse a single property card from search results."""
        # Extract link to detail page
        link_el = (
            card.select_one("a[href*='/kodate/']")
            or card.select_one("a[href*='/chuko/']")
            or card.select_one("a[href*='/home/']")
            or card.select_one("a[href]")
        )
        if not link_el:
            return None

        href = link_el.get("href", "")
        if isinstance(href, list):
            href = href[0]
        if not href.startswith("http"):
            href = f"{self.base_url}{href}"

        # Filter out non-detail links (e.g. pagination, category pages)
        if not re.search(r"/\d{4,}", href):
            return None

        # Extract source ID from URL
        source_id = self._extract_source_id(href)

        # Extract price
        price = self._extract_price(card)

        # Extract address
        address = self._extract_address(card)

        # Extract basic details from table cells
        raw_data = self._extract_raw_data(card)

        # Extract land/building area, floor plan, year from raw data
        land_area = None
        building_area = None
        floor_plan = None
        year_built = None

        for key, value in raw_data.items():
            key_lower = key.strip()
            # Land area
            if not land_area and ("土地" in key_lower or "敷地" in key_lower):
                land_area = self._parse_area(value)
            # Building area
            if not building_area and (
                "建物" in key_lower or "延床" in key_lower or "専有" in key_lower
            ):
                building_area = self._parse_area(value)
            # Floor plan (間取り)
            if not floor_plan and (
                "間取" in key_lower
                or re.search(r"\d+[SLDK]+", value)
            ):
                plan_match = re.search(r"\d+[SLDK]+", value)
                if plan_match:
                    floor_plan = plan_match.group(0)
                elif "間取" in key_lower:
                    floor_plan = value.strip()
            # Year built
            if not year_built and ("築" in key_lower or "建築" in key_lower or "年" in key_lower):
                year_built = self._parse_year(value)

        # Also scan unstructured values for area / floor plan / year
        for value in raw_data.values():
            if not land_area:
                land_area = self._parse_area(value)
            if not floor_plan:
                plan_match = re.search(r"\d+[SLDK]+", value)
                if plan_match:
                    floor_plan = plan_match.group(0)
            if not year_built:
                year_match = re.search(r"(\d{4})年", value)
                if year_match:
                    year_built = int(year_match.group(1))

        # Must have at least address or price to be valid
        if not address and not price:
            return None

        return RawListing(
            source="athome",
            source_id=source_id,
            source_url=href,
            title=self._extract_title(card),
            price=price,
            address=address,
            land_area_sqm=land_area,
            building_area_sqm=building_area,
            floor_plan=floor_plan,
            year_built=year_built,
            raw_data=raw_data,
        )

    def _extract_source_id(self, url: str) -> str:
        """Extract unique listing ID from at home URL."""
        # at home URLs typically contain a numeric property ID
        match = re.search(r"/(\d{5,})/?", url)
        if match:
            return match.group(1)
        # Fallback: last path segment
        match = re.search(r"/([A-Za-z0-9_-]+)/?(?:\?|$)", url.rstrip("/"))
        return match.group(1) if match else url

    def _extract_title(self, card: Tag) -> str | None:
        """Extract listing title."""
        for selector in [
            "h2",
            "h3",
            "[class*='title']",
            "[class*='name']",
            "[class*='heading']",
            "a",
        ]:
            el = card.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if text and len(text) > 3:
                    return text
        return None

    def _extract_price(self, card: Tag) -> int | None:
        """Extract price from a card element."""
        for selector in [
            "[class*='price']",
            "[class*='Price']",
            "[class*='kakaku']",
            ".price",
            ".value",
            "span.num",
        ]:
            el = card.select_one(selector)
            if el:
                price = self._parse_price(el.get_text(strip=True))
                if price:
                    return price

        # Fallback: search all text for price patterns
        card_text = card.get_text()
        price = self._parse_price(card_text)
        return price

    def _extract_address(self, card: Tag) -> str | None:
        """Extract address from a card element."""
        for selector in [
            "[class*='address']",
            "[class*='Address']",
            "[class*='shozaichi']",
            "[class*='area']",
            "[class*='location']",
        ]:
            el = card.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                # Validate it looks like a Japanese address
                if re.search(r"[都道府県市区町村郡]", text):
                    return text

        # Fallback: look for address patterns in th/td pairs
        for row in card.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                label = th.get_text(strip=True)
                if "所在地" in label or "住所" in label:
                    return td.get_text(strip=True)

        # Fallback: look in dt/dd pairs
        for dt in card.select("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                label = dt.get_text(strip=True)
                if "所在地" in label or "住所" in label:
                    return dd.get_text(strip=True)

        return None

    def _extract_raw_data(self, card: Tag) -> dict[str, str]:
        """Extract all text data from table cells in the card."""
        raw_data: dict[str, str] = {}
        # Try th/td pairs first
        for row in card.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                raw_data[th.get_text(strip=True)] = td.get_text(strip=True)

        # Also try dt/dd pairs
        for dt in card.select("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                raw_data[dt.get_text(strip=True)] = dd.get_text(strip=True)

        # If no structured data found, collect all text cells
        if not raw_data:
            for i, cell in enumerate(card.select("td, dd, span, p")):
                text = cell.get_text(strip=True)
                if text and len(text) > 1:
                    raw_data[f"field_{i}"] = text

        return raw_data

    def _parse_price(self, text: str) -> int | None:
        """
        Parse Japanese price text to yen integer.

        Supports formats:
          - 1億5000万円  (150,000,000)
          - 1億円        (100,000,000)
          - 1500万円     (15,000,000)
          - 150万円      (1,500,000)
          - 1500000円    (1,500,000)
        """
        text = text.replace(",", "").replace(" ", "").replace("\u3000", "")

        # Pattern: 1億5000万円 or 1億万円 or 1億円
        oku_match = re.search(r"(\d+)億(?:(\d+)万)?円?", text)
        if oku_match:
            total = int(oku_match.group(1)) * 100_000_000
            if oku_match.group(2):
                total += int(oku_match.group(2)) * 10_000
            return total

        # Pattern: 1500万円 or 150万円
        man_match = re.search(r"(\d+)万円?", text)
        if man_match:
            return int(man_match.group(1)) * 10_000

        # Pattern: 1500000円 (plain yen)
        yen_match = re.search(r"(\d{4,})円", text)
        if yen_match:
            return int(yen_match.group(1))

        return None

    def _parse_area(self, text: str) -> float | None:
        """
        Parse area text to square metres.

        Supports formats:
          - 100.5m2  / 100.5m²  / 100.5㎡
          - 100.5 m2 / 100.5 m² / 100.5 ㎡
        """
        match = re.search(r"([\d.]+)\s*[m㎡²]", text)
        return float(match.group(1)) if match else None

    def _parse_year(self, text: str) -> int | None:
        """
        Parse year from Japanese date text.

        Supports both Western calendar (西暦) and Japanese era (和暦):
          - 2005年, 2005年3月
          - 令和5年, 平成17年, 昭和60年, 大正15年
        """
        # Western year: 2005年
        match = re.search(r"(\d{4})年", text)
        if match:
            return int(match.group(1))

        # Japanese era: 令和5年, 平成17年, 昭和60年
        era_map = {
            "令和": 2018,
            "平成": 1988,
            "昭和": 1925,
            "大正": 1911,
        }
        for era, base in era_map.items():
            match = re.search(rf"{era}(\d+)年", text)
            if match:
                return base + int(match.group(1))

        return None

    def _parse_float(self, text: str) -> float | None:
        """Parse a float from text."""
        match = re.search(r"([\d.]+)", text)
        return float(match.group(1)) if match else None

    async def scrape_detail(self, listing_url: str) -> RawListing | None:
        """Scrape an at home detail page for full property information."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ja-JP",
            )
            pw_page = await context.new_page()

            try:
                await pw_page.goto(
                    listing_url, wait_until="domcontentloaded", timeout=30000
                )
                await pw_page.wait_for_timeout(2000)
                html = await pw_page.content()
                return self._parse_detail_page(html, listing_url)
            except Exception as e:
                logger.warning(
                    "at home detail scrape failed", url=listing_url, error=str(e)
                )
                return None
            finally:
                await browser.close()

    def _parse_detail_page(self, html: str, url: str) -> RawListing | None:
        """Parse an at home detail page for complete property data."""
        soup = BeautifulSoup(html, "lxml")

        # Extract all key-value pairs from detail tables
        details: dict[str, str] = {}
        for row in soup.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                key = th.get_text(strip=True)
                value = td.get_text(strip=True)
                if key and value:
                    details[key] = value

        # Also check dl/dt/dd pairs
        for dt in soup.select("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                key = dt.get_text(strip=True)
                value = dd.get_text(strip=True)
                if key and value:
                    details[key] = value

        # --- Price ---
        price = None
        for key in ["販売価格", "価格", "物件価格"]:
            if key in details:
                price = self._parse_price(details[key])
                if price:
                    break

        # Fallback: price from dedicated price element on page
        if not price:
            for selector in ["[class*='price']", "[class*='Price']", "[class*='kakaku']"]:
                el = soup.select_one(selector)
                if el:
                    price = self._parse_price(el.get_text(strip=True))
                    if price:
                        break

        # --- Address ---
        address = None
        for key in ["所在地", "住所", "物件所在地"]:
            if key in details:
                address = details[key]
                break

        # --- Prefecture / Municipality ---
        prefecture = None
        municipality = None
        if address:
            pref_match = re.search(
                r"(北海道|東京都|大阪府|京都府|.{2,3}県)", address
            )
            if pref_match:
                prefecture = pref_match.group(1)
            muni_match = re.search(
                r"(?:北海道|東京都|大阪府|京都府|.{2,3}県)(.+?[市区町村郡])", address
            )
            if muni_match:
                municipality = muni_match.group(1)

        # --- Areas ---
        land_area = None
        for key in ["土地面積", "敷地面積", "土地"]:
            if key in details:
                land_area = self._parse_area(details[key])
                if land_area:
                    break

        building_area = None
        for key in ["建物面積", "延床面積", "専有面積", "建物"]:
            if key in details:
                building_area = self._parse_area(details[key])
                if building_area:
                    break

        # --- Year built ---
        year_built = None
        for key in ["築年月", "建築年月", "建築年", "完成時期", "築年数"]:
            if key in details:
                year_built = self._parse_year(details[key])
                if year_built:
                    break

        # --- Structure ---
        structure = None
        for key in ["構造", "建物構造", "構造・工法"]:
            if key in details:
                structure = details[key]
                break

        # --- Floors ---
        floors = None
        for key in ["階建", "階数", "建物階数"]:
            if key in details:
                floors_match = re.search(r"(\d+)\s*階", details[key])
                if floors_match:
                    floors = int(floors_match.group(1))
                break

        # --- Floor plan ---
        floor_plan = None
        for key in ["間取り", "間取"]:
            if key in details:
                floor_plan = details[key]
                break

        # --- Road info ---
        road_width = None
        for key in ["前面道路幅員", "接道状況", "道路幅員", "前面道路"]:
            if key in details:
                road_width = self._parse_float(details[key])
                if road_width:
                    break

        road_frontage = None
        for key in ["接道間口", "間口"]:
            if key in details:
                road_frontage = self._parse_float(details[key])
                if road_frontage:
                    break

        # --- Zoning ---
        city_planning_zone = None
        for key in ["都市計画", "都市計画区域"]:
            if key in details:
                city_planning_zone = details[key]
                break

        use_zone = None
        for key in ["用途地域"]:
            if key in details:
                use_zone = details[key]
                break

        coverage_ratio = None
        for key in ["建ぺい率", "建蔽率"]:
            if key in details:
                coverage_ratio = self._parse_float(details[key])
                if coverage_ratio:
                    break

        floor_area_ratio = None
        for key in ["容積率"]:
            if key in details:
                floor_area_ratio = self._parse_float(details[key])
                break

        # --- Rebuild status ---
        rebuild_possible = None
        for key in ["備考", "条件", "その他", "再建築", "建築条件", "特記事項"]:
            if key in details:
                text = details[key]
                if "再建築不可" in text:
                    rebuild_possible = False
                elif "再建築可" in text:
                    rebuild_possible = True

        # --- Coordinates ---
        latitude = None
        longitude = None
        # at home sometimes embeds lat/lng in script tags or data attributes
        for script in soup.select("script"):
            script_text = script.string or ""
            lat_match = re.search(r"[\"']?lat(?:itude)?[\"']?\s*[:=]\s*([\d.]+)", script_text)
            lng_match = re.search(r"[\"']?lng|lon(?:gitude)?[\"']?\s*[:=]\s*([\d.]+)", script_text)
            if lat_match and lng_match:
                try:
                    latitude = float(lat_match.group(1))
                    longitude = float(lng_match.group(1))
                except (ValueError, IndexError):
                    pass
                break

        # Also check data attributes on map elements
        map_el = soup.select_one("[data-lat][data-lng], [data-latitude][data-longitude]")
        if map_el and latitude is None:
            lat_attr = map_el.get("data-lat") or map_el.get("data-latitude")
            lng_attr = map_el.get("data-lng") or map_el.get("data-longitude")
            if lat_attr and lng_attr:
                try:
                    latitude = float(lat_attr if isinstance(lat_attr, str) else lat_attr[0])
                    longitude = float(lng_attr if isinstance(lng_attr, str) else lng_attr[0])
                except (ValueError, IndexError):
                    pass

        # --- Images ---
        image_urls: list[str] = []
        for img in soup.select(
            "img[src*='athome.co.jp'], "
            "img[data-src*='athome.co.jp'], "
            "img[src*='athome-inc'], "
            "img[data-src*='athome-inc']"
        ):
            src = img.get("data-src") or img.get("src")
            if src and isinstance(src, str) and src not in image_urls:
                # Skip tiny icons and UI images
                if "icon" not in src.lower() and "logo" not in src.lower():
                    image_urls.append(src)

        # Also look for background-image style photos
        for el in soup.select("[style*='background-image']"):
            style = el.get("style", "")
            if isinstance(style, str):
                bg_match = re.search(r"url\(['\"]?(https?://[^)'\"]+'?)\)?", style)
                if bg_match:
                    bg_url = bg_match.group(1).strip("'\"")
                    if bg_url not in image_urls:
                        image_urls.append(bg_url)

        source_id = self._extract_source_id(url)

        # --- Title ---
        title = None
        for selector in ["h1", "[class*='heading']", "[class*='title']", ".section_h1"]:
            el = soup.select_one(selector)
            if el:
                title = el.get_text(strip=True)
                if title:
                    break

        return RawListing(
            source="athome",
            source_id=source_id,
            source_url=url,
            title=title,
            price=price,
            address=address,
            prefecture=prefecture,
            municipality=municipality,
            land_area_sqm=land_area,
            building_area_sqm=building_area,
            floor_plan=floor_plan,
            year_built=year_built,
            structure=structure,
            floors=floors,
            road_width_m=road_width,
            road_frontage_m=road_frontage,
            rebuild_possible=rebuild_possible,
            city_planning_zone=city_planning_zone,
            use_zone=use_zone,
            coverage_ratio=coverage_ratio,
            floor_area_ratio=floor_area_ratio,
            latitude=latitude,
            longitude=longitude,
            image_urls=image_urls[:10],
            raw_data=details,
        )
