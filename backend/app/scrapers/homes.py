"""
HOME'S (homes.co.jp) scraper for used detached houses (中古戸建).

HOME'S is one of Japan's largest real-estate portals, operated by LIFULL.
This scraper targets the 中古戸建 (used detached house) section:
1. Navigates the 中古戸建 search with price/area filters
2. Paginates through search results
3. Extracts listing data from search result cards
4. Scrapes detail pages for additional data (road, zoning, etc.)

Uses Playwright for JS-rendered content.
Crawl delay: 5s between pages (respecting server load).
"""

import json
import re

import structlog
from bs4 import BeautifulSoup, Tag

from app.scrapers.base import AbstractScraper, RawListing, SearchParams
from app.scrapers.registry import register_scraper

logger = structlog.get_logger()

# Map JIS prefecture codes to HOME'S URL slug names
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


@register_scraper("homes")
class HomesScraper(AbstractScraper):
    """Scraper for HOME'S (homes.co.jp) 中古戸建 (used detached houses)."""

    source_id = "homes"
    base_url = "https://www.homes.co.jp"
    crawl_delay_seconds = 5.0

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------

    def _build_search_url(self, params: SearchParams, page: int = 1) -> str:
        """
        Build HOME'S search URL for used detached houses.

        URL pattern:
            https://www.homes.co.jp/kodate/chu/{prefecture}/list/?page={page}&price_max={price_man}

        price_max is expressed in 万円 (10,000 yen units).
        """
        prefecture_code = params.prefecture_code or "13"
        prefecture_name = PREFECTURE_NAMES.get(prefecture_code, "tokyo")

        # HOME'S expects the price ceiling in 万円 (man-en)
        price_man = params.price_max // 10_000

        url = (
            f"{self.base_url}/kodate/chu/{prefecture_name}/list/"
            f"?page={page}&price_max={price_man}"
        )
        return url

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_listings(self, params: SearchParams) -> list[RawListing]:
        """Search HOME'S for 中古戸建 listings matching *params*."""
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
                    logger.info("Scraping HOME'S page", page=page_num, url=url)

                    await pw_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await pw_page.wait_for_timeout(3000)

                    html = await pw_page.content()
                    page_listings = self._parse_search_results(html)

                    if not page_listings:
                        logger.info("No more results", page=page_num)
                        break

                    listings.extend(page_listings)
                    logger.info(
                        "Parsed HOME'S page",
                        page=page_num,
                        count=len(page_listings),
                        total=len(listings),
                    )

                    # Check if there is a next page
                    if not self._has_next_page(html):
                        logger.info("Reached last page", page=page_num)
                        break

                    await self._delay()

            except Exception as e:
                logger.error("HOME'S search failed", error=str(e))
                raise
            finally:
                await browser.close()

        return listings

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _has_next_page(self, html: str) -> bool:
        """Check if there are more pages of results."""
        soup = BeautifulSoup(html, "lxml")
        # HOME'S pagination: look for "次へ" link or a rel="next" anchor
        next_link = soup.select_one(
            "a[rel='next'], "
            "a.pagination-next, "
            "[class*='pagination'] a[class*='next']"
        )
        if next_link:
            return True
        # Fallback: look for text-based "次へ" link
        for a_tag in soup.select("[class*='pagination'] a, .pager a"):
            if "次へ" in a_tag.get_text():
                return True
        return False

    # ------------------------------------------------------------------
    # Search-result parsing
    # ------------------------------------------------------------------

    def _parse_search_results(self, html: str) -> list[RawListing]:
        """Parse HOME'S search results page HTML into listing objects."""
        soup = BeautifulSoup(html, "lxml")
        listings: list[RawListing] = []

        # HOME'S uses card-style containers; try several selector patterns
        property_cards = (
            soup.select(".mod-mergeBuilding")
            or soup.select(".mod-buildingListUnit")
            or soup.select("[class*='building']")
            or soup.select(".prg-building")
        )

        if not property_cards:
            # Broad fallback: find anchors linking to individual property pages
            # and collect their parent containers
            property_cards = []
            for link in soup.select("a[href*='/kodate/chu/']"):
                parent = link.find_parent(["div", "li", "article", "section"])
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
        # ----- detail-page link -----
        link_el = (
            card.select_one("a[href*='/kodate/chu/']")
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

        source_id = self._extract_source_id(href)

        # ----- price -----
        price = self._extract_price(card)

        # ----- address -----
        address = self._extract_address(card)

        # ----- structured data from table cells -----
        raw_data = self._extract_raw_data(card)

        # Derive land area, building area, floor plan and year from raw_data
        land_area: float | None = None
        building_area: float | None = None
        floor_plan: str | None = None
        year_built: int | None = None

        for key, value in raw_data.items():
            key_lower = key.strip()
            if "土地" in key_lower and not land_area:
                land_area = self._parse_area(value)
            elif "建物" in key_lower and not building_area:
                building_area = self._parse_area(value)
            elif not land_area and not building_area:
                # Also try to pull area from unlabelled values
                area_val = self._parse_area(value)
                if area_val and not land_area:
                    land_area = area_val
            if re.search(r"\d+[SLDK]+", value) and not floor_plan:
                floor_plan = value.strip()
            if not year_built:
                year_built = self._parse_year(value)

        # Must have at least an address or price to be useful
        if not address and not price:
            return None

        return RawListing(
            source="homes",
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

    # ------------------------------------------------------------------
    # Detail-page scraping
    # ------------------------------------------------------------------

    async def scrape_detail(self, listing_url: str) -> RawListing | None:
        """Scrape a HOME'S detail page for full property information."""
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
                    "Detail scrape failed", url=listing_url, error=str(e)
                )
                return None
            finally:
                await browser.close()

    def _parse_detail_page(self, html: str, url: str) -> RawListing | None:
        """Parse a HOME'S detail page for complete property data."""
        soup = BeautifulSoup(html, "lxml")

        # ---- ld+json structured data (if present) ----
        ld_data = self._extract_ld_json(soup)

        # ---- key/value pairs from HTML tables ----
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

        # ---- Price ----
        price = None
        for key in ["販売価格", "価格", "物件価格"]:
            if key in details:
                price = self._parse_price(details[key])
                if price:
                    break
        # Fallback: ld+json price
        if not price and ld_data:
            ld_price = (
                ld_data.get("offers", {}).get("price")
                if isinstance(ld_data.get("offers"), dict)
                else None
            )
            if ld_price:
                try:
                    price = int(float(ld_price))
                except (ValueError, TypeError):
                    pass

        # ---- Address ----
        address = (
            details.get("所在地")
            or details.get("住所")
            or details.get("物件所在地")
        )
        if not address and ld_data:
            ld_addr = ld_data.get("address")
            if isinstance(ld_addr, dict):
                parts = [
                    ld_addr.get("addressRegion", ""),
                    ld_addr.get("addressLocality", ""),
                    ld_addr.get("streetAddress", ""),
                ]
                composed = "".join(p for p in parts if p)
                if composed:
                    address = composed
            elif isinstance(ld_addr, str) and ld_addr:
                address = ld_addr

        # ---- Areas ----
        land_area = self._parse_area(details.get("土地面積", ""))
        building_area = self._parse_area(
            details.get("建物面積", details.get("延床面積", details.get("専有面積", "")))
        )

        # ---- Year built ----
        year_built = None
        for key in ["築年月", "建築年月", "建築年", "完成時期"]:
            if key in details:
                year_built = self._parse_year(details[key])
                if year_built:
                    break

        # ---- Structure ----
        structure = (
            details.get("構造")
            or details.get("建物構造")
            or details.get("構造・工法")
        )

        # ---- Floor plan ----
        floor_plan = details.get("間取り") or details.get("間取")

        # ---- Floors ----
        floors = None
        for key in ["階建", "階数"]:
            if key in details:
                floors = self._parse_int(details[key])
                if floors:
                    break

        # ---- Road info ----
        road_width = self._parse_float(
            details.get("前面道路幅員", details.get("接道状況", ""))
        )
        road_frontage = self._parse_float(details.get("接道間口", ""))

        # ---- Zoning ----
        city_planning_zone = details.get("都市計画")
        use_zone = details.get("用途地域")
        coverage_ratio = self._parse_float(
            details.get("建ぺい率", details.get("建蔽率", ""))
        )
        floor_area_ratio = self._parse_float(details.get("容積率", ""))

        # ---- Rebuild possible ----
        rebuild_possible = None
        for key in ["備考", "条件", "その他", "再建築", "その他制限事項"]:
            if key in details:
                text = details[key]
                if "再建築不可" in text:
                    rebuild_possible = False
                elif "再建築可" in text:
                    rebuild_possible = True

        # ---- Geo coordinates (from ld+json) ----
        latitude = None
        longitude = None
        if ld_data:
            geo = ld_data.get("geo")
            if isinstance(geo, dict):
                try:
                    latitude = float(geo["latitude"])
                    longitude = float(geo["longitude"])
                except (KeyError, ValueError, TypeError):
                    pass

        # ---- Images ----
        image_urls: list[str] = []
        for img in soup.select(
            "img[src*='homes.co.jp'], img[data-src*='homes.co.jp']"
        ):
            src = img.get("data-src") or img.get("src")
            if src and isinstance(src, str) and src not in image_urls:
                if re.search(r"\.(jpe?g|png|webp)", src, re.IGNORECASE):
                    image_urls.append(src)
        # Fallback: ld+json images
        if not image_urls and ld_data:
            ld_images = ld_data.get("image")
            if isinstance(ld_images, list):
                image_urls = [u for u in ld_images if isinstance(u, str)][:10]
            elif isinstance(ld_images, str):
                image_urls = [ld_images]

        # ---- Source ID and title ----
        source_id = self._extract_source_id(url)

        title = None
        for selector in ["h1", "[class*='heading']", "[class*='title']"]:
            el = soup.select_one(selector)
            if el:
                title = el.get_text(strip=True)
                if title:
                    break

        # Derive prefecture / municipality from address
        prefecture, municipality = self._split_address(address)

        return RawListing(
            source="homes",
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

    # ------------------------------------------------------------------
    # ld+json extraction
    # ------------------------------------------------------------------

    def _extract_ld_json(self, soup: BeautifulSoup) -> dict:
        """Extract the first relevant ld+json block from the page."""
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
                # Accept dicts that look like a product or real-estate listing
                if isinstance(data, dict):
                    return data
                # Sometimes it's a list; pick the first dict
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            return item
            except (json.JSONDecodeError, TypeError):
                continue
        return {}

    # ------------------------------------------------------------------
    # Card-level extraction helpers
    # ------------------------------------------------------------------

    def _extract_source_id(self, url: str) -> str:
        """Extract a unique listing ID from a HOME'S URL."""
        # Typical pattern: /kodate/chu/tokyo/1234567/ or ?bid=1234567
        match = re.search(r"/(\d{5,})/?", url)
        if match:
            return match.group(1)
        match = re.search(r"bid=(\d+)", url)
        if match:
            return match.group(1)
        # Last path segment
        match = re.search(r"/([A-Za-z0-9_-]+)/?(?:\?|$)", url.rstrip("/"))
        return match.group(1) if match else url

    def _extract_title(self, card: Tag) -> str | None:
        """Extract listing title from a card."""
        for selector in [
            "h2",
            "[class*='heading']",
            "[class*='title']",
            "[class*='name']",
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
            ".priceLabel",
            ".value",
        ]:
            el = card.select_one(selector)
            if el:
                price = self._parse_price(el.get_text(strip=True))
                if price:
                    return price

        # Fallback: scan the full card text for a price pattern
        card_text = card.get_text()
        return self._parse_price(card_text)

    def _extract_address(self, card: Tag) -> str | None:
        """Extract address from a card element."""
        for selector in [
            "[class*='address']",
            "[class*='Address']",
            "[class*='area']",
            "[class*='location']",
        ]:
            el = card.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if re.search(r"[都道府県市区町村郡]", text):
                    return text
        return None

    def _extract_raw_data(self, card: Tag) -> dict[str, str]:
        """Extract all key-value text pairs from a card (tables, dl lists, etc.)."""
        raw_data: dict[str, str] = {}

        # th/td pairs
        for row in card.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                raw_data[th.get_text(strip=True)] = td.get_text(strip=True)

        # dt/dd pairs
        for dt in card.select("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                raw_data[dt.get_text(strip=True)] = dd.get_text(strip=True)

        # If nothing found, gather all text cells as fallback
        if not raw_data:
            for i, cell in enumerate(card.select("td, dd, span, li")):
                text = cell.get_text(strip=True)
                if text and len(text) > 1:
                    raw_data[f"field_{i}"] = text

        return raw_data

    # ------------------------------------------------------------------
    # Value parsers
    # ------------------------------------------------------------------

    def _parse_price(self, text: str) -> int | None:
        """
        Parse Japanese price text to yen integer.

        Supports formats:
        - 1億5000万円  (150,000,000)
        - 1億円        (100,000,000)
        - 1500万円     (15,000,000)
        - 1500000円    (1,500,000)
        """
        text = text.replace(",", "").replace(" ", "").replace("\u3000", "")

        # Pattern: 1億5000万円 or 1億円
        oku_match = re.search(r"(\d+)億(?:(\d+)万)?円?", text)
        if oku_match:
            total = int(oku_match.group(1)) * 100_000_000
            if oku_match.group(2):
                total += int(oku_match.group(2)) * 10_000
            return total

        # Pattern: 1500万円
        man_match = re.search(r"(\d+)万円?", text)
        if man_match:
            return int(man_match.group(1)) * 10_000

        # Pattern: 1500000円 (plain yen, at least 4 digits)
        yen_match = re.search(r"(\d{4,})円", text)
        if yen_match:
            return int(yen_match.group(1))

        return None

    def _parse_area(self, text: str) -> float | None:
        """Parse area text like '100.5m²', '100.5㎡', or '100.5 m2'."""
        match = re.search(r"([\d.]+)\s*[m㎡²]", text)
        return float(match.group(1)) if match else None

    def _parse_year(self, text: str) -> int | None:
        """
        Parse year from Japanese date text.

        Supports:
        - Western year:  2005年, 2005年3月
        - Japanese era:  令和5年, 平成17年, 昭和60年, 大正12年
        """
        # Western year: 2005年
        match = re.search(r"(\d{4})年", text)
        if match:
            return int(match.group(1))

        # Japanese era conversion
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
        """Parse the first float from text."""
        match = re.search(r"([\d.]+)", text)
        return float(match.group(1)) if match else None

    def _parse_int(self, text: str) -> int | None:
        """Parse the first integer from text."""
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else None

    # ------------------------------------------------------------------
    # Address splitting
    # ------------------------------------------------------------------

    def _split_address(self, address: str | None) -> tuple[str | None, str | None]:
        """
        Split a full Japanese address into prefecture and municipality.

        Returns (prefecture, municipality) or (None, None).
        """
        if not address:
            return None, None

        # Match the prefecture portion (東京都, 大阪府, 北海道, or *県)
        pref_match = re.match(
            r"(東京都|北海道|(?:大阪|京都)府|.{2,3}県)", address
        )
        if not pref_match:
            return None, None

        prefecture = pref_match.group(1)
        rest = address[pref_match.end():]

        # Match municipality (市, 区, 町, 村, 郡)
        muni_match = re.match(r"(.+?[市区町村郡])", rest)
        municipality = muni_match.group(1) if muni_match else None

        return prefecture, municipality
