"""
SUUMO (suumo.jp) scraper for used detached houses (中古戸建).

SUUMO is Japan's largest real estate portal. This scraper:
1. Navigates the 中古戸建 search with price/area filters
2. Paginates through search results
3. Extracts listing data from search result cards
4. Scrapes detail pages for additional data (road, zoning, etc.)

Uses Playwright for JS-rendered content.
Crawl delay: 30s between pages (respecting server load).
"""

import re

import structlog
from bs4 import BeautifulSoup, Tag

from app.scrapers.base import AbstractScraper, RawListing, SearchParams
from app.scrapers.registry import register_scraper

logger = structlog.get_logger()

# SUUMO area codes (ar parameter) by region
SUUMO_REGION_CODES = {
    # Hokkaido/Tohoku
    "01": "010", "02": "020", "03": "020", "04": "020", "05": "020",
    "06": "020", "07": "020",
    # Kanto
    "08": "030", "09": "030", "10": "030", "11": "030",
    "12": "030", "13": "030", "14": "030",
    # Chubu
    "15": "040", "16": "040", "17": "040", "18": "040",
    "19": "040", "20": "040", "21": "050", "22": "050",
    "23": "050",
    # Kinki
    "24": "060", "25": "060", "26": "060", "27": "060",
    "28": "060", "29": "060", "30": "060",
    # Chugoku/Shikoku
    "31": "070", "32": "070", "33": "070", "34": "070",
    "35": "070", "36": "080", "37": "080", "38": "080", "39": "080",
    # Kyushu/Okinawa
    "40": "090", "41": "090", "42": "090", "43": "090",
    "44": "090", "45": "090", "46": "090", "47": "090",
}

# SUUMO price code mapping (pc parameter: price ceiling in 万円)
PRICE_CODES = [50, 100, 150, 200, 300, 400, 500, 600, 700, 800, 1000, 1500, 2000, 3000, 5000]


def _price_to_suumo_code(price_yen: int) -> int:
    """Convert yen price to the nearest SUUMO price code (万円)."""
    man = price_yen // 10_000
    for code in PRICE_CODES:
        if man <= code:
            return code
    return PRICE_CODES[-1]


@register_scraper("suumo")
class SuumoScraper(AbstractScraper):
    """Scraper for SUUMO 中古戸建 (used detached houses)."""

    source_id = "suumo"
    base_url = "https://suumo.jp"
    crawl_delay_seconds = 30.0

    def _build_search_url(self, params: SearchParams, page: int = 1) -> str:
        """
        Build SUUMO search URL for used detached houses.

        URL pattern: /jj/bukken/ichiran/JJ012FC001/
        Key parameters:
          ar  = region code (030=Kanto, 060=Kinki, etc.)
          bs  = property type (021=中古戸建)
          ta  = prefecture code (13=Tokyo, 27=Osaka, etc.)
          pc  = price ceiling (万円)
          pj  = page number
          po  = sort order (1=new, 2=price_asc, 3=price_desc)
          cn  = results per page (30, 50, 100)
        """
        prefecture_code = params.prefecture_code or "13"
        ar = SUUMO_REGION_CODES.get(prefecture_code, "030")
        pc = _price_to_suumo_code(params.price_max)

        url = (
            f"{self.base_url}/jj/bukken/ichiran/JJ012FC001/"
            f"?ar={ar}&bs=021&ta={prefecture_code}"
            f"&pc={pc}&cn=50&po=2&page={page}"
        )
        return url

    async def search_listings(self, params: SearchParams) -> list[RawListing]:
        """Search SUUMO for properties matching criteria."""
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
                    logger.info("Scraping SUUMO page", page=page_num, url=url)

                    await pw_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await pw_page.wait_for_timeout(3000)

                    html = await pw_page.content()
                    page_listings = self._parse_search_results(html)

                    if not page_listings:
                        logger.info("No more results", page=page_num)
                        break

                    listings.extend(page_listings)
                    logger.info(
                        "Parsed SUUMO page",
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
                logger.error("SUUMO search failed", error=str(e))
                raise
            finally:
                await browser.close()

        return listings

    def _has_next_page(self, html: str) -> bool:
        """Check if there are more pages of results."""
        soup = BeautifulSoup(html, "lxml")

        # Look for rel="next" link
        if soup.select_one(".pagination_set-nav a[rel='next']"):
            return True

        # Look for "次へ" text in links (BS4 doesn't support :contains)
        for a_tag in soup.select("a"):
            if a_tag.get_text(strip=True) == "次へ":
                return True

        # Check page numbers
        pagination = soup.select(".pagination_set .pagination_set-num")
        return len(pagination) > 1

    def _parse_search_results(self, html: str) -> list[RawListing]:
        """Parse SUUMO search results page HTML."""
        soup = BeautifulSoup(html, "lxml")
        listings: list[RawListing] = []

        # SUUMO 中古戸建 uses cassette-style cards
        # Try multiple selectors for different page layouts
        property_cards = (
            soup.select(".property_unit")
            or soup.select(".cassetteitem")
            or soup.select(".dottable-line")
            or soup.select("[class*='cassette']")
        )

        if not property_cards:
            # Fallback: find any block containing property links
            property_cards = []
            for link in soup.select("a[href*='/chukoikkodate/']"):
                parent = link.find_parent(["div", "li", "tr", "article"])
                if parent and parent not in property_cards:
                    property_cards.append(parent)

        for card in property_cards:
            try:
                listing = self._parse_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.warning("Failed to parse card", error=str(e))

        return listings

    def _parse_card(self, card: Tag) -> RawListing | None:
        """Parse a single property card from search results."""
        # Extract link to detail page
        link_el = (
            card.select_one("a[href*='/chukoikkodate/']")
            or card.select_one("a[href*='/kodate/']")
            or card.select_one("a[href]")
        )
        if not link_el:
            return None

        href = link_el.get("href", "")
        if isinstance(href, list):
            href = href[0]
        if not href.startswith("http"):
            href = f"{self.base_url}{href}"

        # Extract source ID from URL
        source_id = self._extract_source_id(href)

        # Extract price
        price = self._extract_price(card)

        # Extract address
        address = self._extract_address(card)

        # Extract basic details from table cells
        raw_data = self._extract_raw_data(card)

        # Extract land/building area from raw data
        land_area = None
        building_area = None
        floor_plan = None
        year_built = None

        for value in raw_data.values():
            if not land_area:
                land_area = self._parse_area(value)
            if "LDK" in value or "DK" in value or "K" in value:
                floor_plan = value.strip()
            year_match = re.search(r"(\d{4})年", value)
            if year_match and not year_built:
                year_built = int(year_match.group(1))

        # Must have at least address or price to be valid
        if not address and not price:
            return None

        return RawListing(
            source="suumo",
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
        """Extract unique ID from SUUMO URL."""
        # Try common URL patterns
        match = re.search(r"/([A-Za-z0-9]+)/?(?:\?|$)", url.rstrip("/"))
        return match.group(1) if match else url

    def _extract_title(self, card: Tag) -> str | None:
        """Extract listing title."""
        for selector in ["h2", ".property_unit-title", ".cassetteitem_content-title", "a"]:
            el = card.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if text and len(text) > 3:
                    return text
        return None

    def _extract_price(self, card: Tag) -> int | None:
        """Extract price from a card element."""
        for selector in [
            ".dottable-value",
            ".detailnote-price",
            "[class*='price']",
            ".cassetteitem_price",
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
            ".dottable-vm",
            "[class*='address']",
            "[class*='area']",
            ".cassetteitem_detail-col1",
        ]:
            el = card.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                # Validate it looks like a Japanese address
                if re.search(r"[都道府県市区町村郡]", text):
                    return text
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
            for i, cell in enumerate(card.select("td, dd, .detailnote-value, span")):
                text = cell.get_text(strip=True)
                if text and len(text) > 1:
                    raw_data[f"field_{i}"] = text

        return raw_data

    def _parse_price(self, text: str) -> int | None:
        """Parse Japanese price text to yen integer."""
        text = text.replace(",", "").replace(" ", "").replace("\u3000", "")

        # Pattern: 1億5000万円 or 1億万円
        oku_match = re.search(r"(\d+)億(?:(\d+)万)?円?", text)
        if oku_match:
            total = int(oku_match.group(1)) * 100_000_000
            if oku_match.group(2):
                total += int(oku_match.group(2)) * 10_000
            return total

        # Pattern: 150万円 or 1500万円
        man_match = re.search(r"(\d+)万円?", text)
        if man_match:
            return int(man_match.group(1)) * 10_000

        # Pattern: 1500000円 (plain yen)
        yen_match = re.search(r"(\d{4,})円", text)
        if yen_match:
            return int(yen_match.group(1))

        return None

    def _parse_area(self, text: str) -> float | None:
        """Parse area text like '100.5m²' or '100.5㎡'."""
        match = re.search(r"([\d.]+)\s*[m㎡²]", text)
        return float(match.group(1)) if match else None

    def _parse_float(self, text: str) -> float | None:
        """Parse a float from text."""
        match = re.search(r"([\d.]+)", text)
        return float(match.group(1)) if match else None

    async def scrape_detail(self, listing_url: str) -> RawListing | None:
        """Scrape a SUUMO detail page for full property information."""
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
                await pw_page.goto(listing_url, wait_until="domcontentloaded", timeout=30000)
                await pw_page.wait_for_timeout(2000)
                html = await pw_page.content()
                return self._parse_detail_page(html, listing_url)
            except Exception as e:
                logger.warning("Detail scrape failed", url=listing_url, error=str(e))
                return None
            finally:
                await browser.close()

    def _parse_detail_page(self, html: str, url: str) -> RawListing | None:
        """Parse a SUUMO detail page for complete property data."""
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

        # Price (multiple possible labels)
        price = None
        for key in ["販売価格", "価格", "物件価格"]:
            if key in details:
                price = self._parse_price(details[key])
                if price:
                    break

        # Address
        address = details.get("所在地") or details.get("住所") or details.get("物件所在地")

        # Areas
        land_area = self._parse_area(details.get("土地面積", ""))
        building_area = self._parse_area(
            details.get("建物面積", details.get("延床面積", details.get("専有面積", "")))
        )

        # Year built (handles formats: 2005年3月, 平成17年, etc.)
        year_built = None
        for key in ["築年月", "建築年月", "建築年", "完成時期"]:
            if key in details:
                year_built = self._parse_year(details[key])
                if year_built:
                    break

        # Structure
        structure = details.get("構造") or details.get("建物構造") or details.get("構造・工法")

        # Floor plan
        floor_plan = details.get("間取り") or details.get("間取")

        # Road info
        road_width = self._parse_float(details.get("前面道路幅員", details.get("接道状況", "")))
        road_frontage = self._parse_float(details.get("接道間口", ""))

        # Zoning
        city_planning_zone = details.get("都市計画")
        use_zone = details.get("用途地域")
        coverage_ratio = self._parse_float(details.get("建ぺい率", details.get("建蔽率", "")))
        floor_area_ratio = self._parse_float(details.get("容積率", ""))

        # Check rebuild status from remarks
        rebuild_possible = None
        for key in ["備考", "条件", "その他", "再建築"]:
            if key in details:
                text = details[key]
                if "再建築不可" in text:
                    rebuild_possible = False
                elif "再建築可" in text:
                    rebuild_possible = True

        # Images
        image_urls = []
        for img in soup.select("img[src*='img.suumo'], img[data-src*='img.suumo']"):
            src = img.get("data-src") or img.get("src")
            if src and isinstance(src, str) and src not in image_urls:
                image_urls.append(src)

        source_id = self._extract_source_id(url)

        # Title
        title = None
        for selector in ["h1", ".section_h1", "[class*='heading']"]:
            el = soup.select_one(selector)
            if el:
                title = el.get_text(strip=True)
                if title:
                    break

        return RawListing(
            source="suumo",
            source_id=source_id,
            source_url=url,
            title=title,
            price=price,
            address=address,
            land_area_sqm=land_area,
            building_area_sqm=building_area,
            floor_plan=floor_plan,
            year_built=year_built,
            structure=structure,
            road_width_m=road_width,
            road_frontage_m=road_frontage,
            rebuild_possible=rebuild_possible,
            city_planning_zone=city_planning_zone,
            use_zone=use_zone,
            coverage_ratio=coverage_ratio,
            floor_area_ratio=floor_area_ratio,
            image_urls=image_urls[:10],
            raw_data=details,
        )

    def _parse_year(self, text: str) -> int | None:
        """Parse year from Japanese date text (supports 西暦 and 和暦)."""
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
