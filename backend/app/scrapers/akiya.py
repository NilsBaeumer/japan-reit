"""Akiya banks (空き家バンク) scraper.

Akiya banks are municipality-run vacant-house registries.  Unlike commercial
portals they typically serve plain server-rendered HTML, so a simple HTTP
client (httpx) plus BeautifulSoup is sufficient -- no browser automation
required.

Primary aggregation portal: https://www.akiya-athome.jp

Search flow (2026):
    1. Fetch municipality codes: /bukken/search/areas/?search_type=area&br_kbn=buy&sbt_kbn=house&pref_cd={code}
    2. Search with municipality codes: /bukken/search/list/?search_type=area&br_kbn=buy&sbt_kbn=house&pref_cd={code}&gyosei_cd[]={muni}

Crawl delay: 3 seconds (lighter pages than JS-rendered portals).
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin

import httpx
import structlog
from bs4 import BeautifulSoup, Tag

from app.scrapers.base import AbstractScraper, RawListing, SearchParams
from app.scrapers.registry import register_scraper

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Prefecture code -> Japanese name lookup (used for populating RawListing)
# ---------------------------------------------------------------------------
_PREFECTURE_NAMES: dict[str, str] = {
    "01": "北海道", "02": "青森県", "03": "岩手県", "04": "宮城県",
    "05": "秋田県", "06": "山形県", "07": "福島県", "08": "茨城県",
    "09": "栃木県", "10": "群馬県", "11": "埼玉県", "12": "千葉県",
    "13": "東京都", "14": "神奈川県", "15": "新潟県", "16": "富山県",
    "17": "石川県", "18": "福井県", "19": "山梨県", "20": "長野県",
    "21": "岐阜県", "22": "静岡県", "23": "愛知県", "24": "三重県",
    "25": "滋賀県", "26": "京都府", "27": "大阪府", "28": "兵庫県",
    "29": "奈良県", "30": "和歌山県", "31": "鳥取県", "32": "島根県",
    "33": "岡山県", "34": "広島県", "35": "山口県", "36": "徳島県",
    "37": "香川県", "38": "愛媛県", "39": "高知県", "40": "福岡県",
    "41": "佐賀県", "42": "長崎県", "43": "熊本県", "44": "大分県",
    "45": "宮崎県", "46": "鹿児島県", "47": "沖縄県",
}

# Default HTTP headers - polite, identifiable request
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}

# ---------------------------------------------------------------------------
# Japanese-era year conversion (duplicated here to keep the scraper
# self-contained; the canonical version lives in app.utils.date_helpers)
# ---------------------------------------------------------------------------
_ERA_BASE: dict[str, int] = {
    "令和": 2018,
    "平成": 1988,
    "昭和": 1925,
    "大正": 1911,
    "明治": 1867,
}

_ERA_PATTERN = re.compile(r"(令和|平成|昭和|大正|明治)\s*(\d+)\s*年")


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------

def _parse_price(text: str) -> int | None:
    """Parse a Japanese price string and return an integer in yen.

    Supports:
    - 0円 / 無料 / 譲渡 (free properties)
    - 1億5000万円 (oku + man)
    - 150万円 / 1500万円 (man-en)
    - 1500000円 (plain yen)
    - 価格未定 (undecided) -> None
    """
    if not text:
        return None

    text = text.replace(",", "").replace(" ", "").replace("\u3000", "").strip()

    # Free / donated properties
    if re.search(r"(無料|無償|0円|譲渡)", text):
        return 0

    # Price undecided
    if re.search(r"(未定|要相談|応相談|お問[い合]合わせ)", text):
        return None

    # Pattern: N億M万円
    oku_match = re.search(r"(\d+)\s*億(?:\s*(\d+)\s*万)?円?", text)
    if oku_match:
        total = int(oku_match.group(1)) * 100_000_000
        if oku_match.group(2):
            total += int(oku_match.group(2)) * 10_000
        return total

    # Pattern: N万円 (e.g. 150万円, 1500万円)
    man_match = re.search(r"(\d+)\s*万\s*円?", text)
    if man_match:
        return int(man_match.group(1)) * 10_000

    # Pattern: plain yen (e.g. 1500000円)
    yen_match = re.search(r"(\d{3,})円", text)
    if yen_match:
        return int(yen_match.group(1))

    # Bare number that looks like yen
    bare_match = re.search(r"(\d{4,})", text)
    if bare_match:
        return int(bare_match.group(1))

    return None


def _parse_area(text: str) -> float | None:
    """Parse area text like '100.5m²', '100.5㎡', '100.5 m2'."""
    if not text:
        return None
    match = re.search(r"([\d,.]+)\s*[m㎡²]", text)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _parse_year(text: str) -> int | None:
    """Parse a year from Japanese text (Western or era format).

    Examples:
        "2005年3月"  -> 2005
        "平成17年"   -> 2005
        "昭和50年"   -> 1975
        "築45年"     -> None (relative age, not absolute year)
    """
    if not text:
        return None

    # Western year: 2005年, 1990年築 etc.
    western = re.search(r"(\d{4})\s*年", text)
    if western:
        year = int(western.group(1))
        if 1868 <= year <= 2100:
            return year

    # Japanese era: 令和5年, 平成17年, 昭和60年
    era_match = _ERA_PATTERN.search(text)
    if era_match:
        era_name = era_match.group(1)
        era_year = int(era_match.group(2))
        base = _ERA_BASE.get(era_name)
        if base is not None:
            return base + era_year

    return None


def _parse_float(text: str) -> float | None:
    """Parse the first decimal or integer number from *text*."""
    if not text:
        return None
    match = re.search(r"([\d,.]+)", text)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _extract_text(tag: Tag | None) -> str:
    """Safely extract stripped text from a tag (returns '' if tag is None)."""
    if tag is None:
        return ""
    return tag.get_text(strip=True)


def _extract_source_id(url: str) -> str:
    """Derive a stable source_id from an akiya-athome detail URL.

    Typical URL shapes:
        https://okutama-t13308.akiya-athome.jp/bukken/detail/buy/43556
        https://www.akiya-athome.jp/buy/detail/12345
    We extract the trailing numeric segment.
    """
    # Try to grab a trailing numeric ID
    match = re.search(r"/(\d+)/?(?:\?.*)?$", url.rstrip("/"))
    if match:
        return f"akiya-{match.group(1)}"
    # Fallback: last path segment
    parts = url.rstrip("/").split("/")
    return f"akiya-{parts[-1]}" if parts else url


def _prefecture_from_address(address: str) -> str | None:
    """Extract the prefecture name from a Japanese address string."""
    match = re.match(r"(北海道|.{2,3}[都道府県])", address)
    return match.group(1) if match else None


def _municipality_from_address(address: str) -> str | None:
    """Extract municipality (市区町村) from a Japanese address string."""
    match = re.search(r"[都道府県](.*?[市区町村郡])", address)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Scraper class
# ---------------------------------------------------------------------------

@register_scraper("akiya")
class AkiyaScraper(AbstractScraper):
    """Scraper for Akiya banks (空き家バンク) via the akiya-athome aggregation
    portal.  Pages are server-rendered HTML; uses ``httpx`` + ``BeautifulSoup``
    (no Playwright needed).
    """

    source_id = "akiya"
    base_url = "https://www.akiya-athome.jp"
    crawl_delay_seconds = 3.0

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------

    def _build_search_url(
        self,
        params: SearchParams,
        municipality_codes: list[str] | None = None,
        page: int = 1,
    ) -> str:
        """Build the akiya-athome search URL.

        URL pattern (2026):
            /bukken/search/list/?search_type=area&br_kbn=buy&sbt_kbn=house
            &pref_cd={code}&gyosei_cd[]={muni}&item_count=100&page={page}
        """
        prefecture_code = (params.prefecture_code or "13").zfill(2)

        url = (
            f"{self.base_url}/bukken/search/list/"
            f"?search_type=area&br_kbn=buy&sbt_kbn=house"
            f"&pref_cd={prefecture_code}"
        )

        if municipality_codes:
            for code in municipality_codes:
                url += f"&gyosei_cd[]={code}"

        url += "&item_count=100&search_sort=kokai_date"

        if page > 1:
            url += f"&page={page}"

        return url

    # ------------------------------------------------------------------
    # Municipality discovery
    # ------------------------------------------------------------------

    async def _fetch_municipality_codes(
        self,
        prefecture_code: str,
        client: httpx.AsyncClient,
    ) -> list[str]:
        """Fetch available municipality codes for a prefecture from the areas page.

        Returns a list of gyosei_cd values (e.g. ['13308']) for municipalities
        that have akiya bank listings.
        """
        url = (
            f"{self.base_url}/bukken/search/areas/"
            f"?search_type=area&br_kbn=buy&sbt_kbn=house"
            f"&pref_cd={prefecture_code}"
        )

        logger.info(
            "Fetching akiya municipality codes",
            url=url,
            prefecture=prefecture_code,
        )

        try:
            response = await client.get(url)
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Failed to fetch municipality codes", error=str(exc))
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        codes: list[str] = []
        for checkbox in soup.select("input[name='gyosei_cd[]']"):
            value = checkbox.get("value")
            if value and isinstance(value, str):
                codes.append(value)

        logger.info(
            "Found municipality codes",
            count=len(codes),
            codes=codes[:10],
        )
        return codes

    # ------------------------------------------------------------------
    # search_listings
    # ------------------------------------------------------------------

    async def search_listings(self, params: SearchParams) -> list[RawListing]:
        """Search akiya-athome for listings matching *params*.

        Flow:
        1. Fetch available municipality codes for the prefecture
        2. Build search URL with all municipality codes
        3. Paginate through results with crawl delay
        """
        listings: list[RawListing] = []
        prefecture_code = (params.prefecture_code or "13").zfill(2)

        async with httpx.AsyncClient(
            headers=_DEFAULT_HEADERS,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        ) as client:
            # Step 1: Discover municipality codes that have listings
            municipality_codes = await self._fetch_municipality_codes(
                prefecture_code, client
            )

            if not municipality_codes:
                logger.warning(
                    "No municipality codes found, trying without",
                    prefecture=prefecture_code,
                )

            await self._delay()

            # Step 2: Paginate through search results
            for page_num in range(1, params.max_pages + 1):
                url = self._build_search_url(
                    params,
                    municipality_codes or None,
                    page_num,
                )
                logger.info(
                    "Fetching akiya search page",
                    page=page_num,
                    url=url[:200],
                )

                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "HTTP error on search page",
                        page=page_num,
                        status=exc.response.status_code,
                        url=url[:200],
                    )
                    break
                except httpx.RequestError as exc:
                    logger.error(
                        "Request error on search page",
                        page=page_num,
                        url=url[:200],
                        error=str(exc),
                    )
                    break

                html = response.text
                page_listings = self._parse_search_results(html, params)

                if not page_listings:
                    logger.info("No more results on page", page=page_num)
                    break

                # Apply price filters client-side (the portal may not support
                # price query params directly)
                for listing in page_listings:
                    if self._passes_price_filter(listing, params):
                        listings.append(listing)

                logger.info(
                    "Parsed akiya search page",
                    page=page_num,
                    found_on_page=len(page_listings),
                    total=len(listings),
                )

                # Check for next page
                if not self._has_next_page(html):
                    logger.info("Reached last page", page=page_num)
                    break

                # Crawl delay between pages
                await self._delay()

        logger.info("Akiya search complete", total_listings=len(listings))
        return listings

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    def _has_next_page(self, html: str) -> bool:
        """Return True if the search-results page has a 'next page' link."""
        soup = BeautifulSoup(html, "html.parser")

        # 1. Pager container with links (2026 layout uses <div class="pager cf">)
        pager = soup.select_one(".pager")
        if pager:
            links = pager.select("a[href]")
            if links:
                return True

        # 2. Explicit "次へ" (next) link text
        for a_tag in soup.select("a"):
            link_text = a_tag.get_text(strip=True)
            if link_text in ("次へ", "次のページ", "次ページ", "next", ">", ">>", "›"):
                return True

        # 3. rel="next" link
        if soup.select_one("a[rel='next']"):
            return True

        # 4. Pagination container with a link beyond current page
        for selector in [".pagination", ".page-nav", "[class*='paginat']",
                         "nav[aria-label*='page']", "ul.page-numbers"]:
            pagination = soup.select_one(selector)
            if pagination:
                page_links = pagination.select("a[href]")
                if len(page_links) >= 1:
                    return True

        return False

    # ------------------------------------------------------------------
    # Price filter (client-side)
    # ------------------------------------------------------------------

    @staticmethod
    def _passes_price_filter(listing: RawListing, params: SearchParams) -> bool:
        """Return True if *listing* falls within the price range in *params*.

        Free properties (price == 0) always pass.  Properties with unknown
        price (None) also pass -- we keep them and let downstream decide.
        """
        if listing.price is None:
            return True
        if listing.price == 0:
            return True
        if params.price_min is not None and listing.price < params.price_min:
            return False
        if params.price_max is not None and listing.price > params.price_max:
            return False
        return True

    # ------------------------------------------------------------------
    # Search results parsing
    # ------------------------------------------------------------------

    def _parse_search_results(
        self,
        html: str,
        params: SearchParams | None = None,
    ) -> list[RawListing]:
        """Parse an akiya-athome search-results page and return RawListings.

        Uses multiple CSS selector fallbacks to handle layout variations.
        """
        soup = BeautifulSoup(html, "html.parser")
        listings: list[RawListing] = []

        # 2026 layout: <section class="propety"> (note the typo in their HTML)
        property_cards: list[Tag] = soup.select("section.propety")

        # Fallback: older selectors
        if not property_cards:
            property_cards = (
                soup.select("article.property-item")
                or soup.select(".akiya-item")
                or soup.select(".property-card")
                or soup.select(".bukken-list li")
                or soup.select(".property_unit")
            )

        # Fallback: find links to detail pages on municipality subdomains
        if not property_cards:
            seen: set[int] = set()
            for link in soup.select("a[href*='/bukken/detail/buy/']"):
                parent = link.find_parent(
                    ["section", "article", "div", "li", "tr"]
                )
                if parent and id(parent) not in seen:
                    seen.add(id(parent))
                    property_cards.append(parent)  # type: ignore[arg-type]

        # Legacy fallback: old-style detail links
        if not property_cards:
            seen = set()
            for link in soup.select("a[href*='/buy/detail/']"):
                parent = link.find_parent(
                    ["article", "div", "li", "section", "tr"]
                )
                if parent and id(parent) not in seen:
                    seen.add(id(parent))
                    property_cards.append(parent)  # type: ignore[arg-type]

        prefecture_code = (params.prefecture_code or "").zfill(2) if params else None

        for card in property_cards:
            try:
                listing = self._parse_card(card, prefecture_code)
                if listing is not None:
                    listings.append(listing)
            except Exception as exc:
                logger.warning("Failed to parse akiya card", error=str(exc))

        return listings

    # ------------------------------------------------------------------
    # Individual card parsing
    # ------------------------------------------------------------------

    def _parse_card(
        self,
        card: Tag,
        prefecture_code: str | None = None,
    ) -> RawListing | None:
        """Parse a single property card from search results into a RawListing.

        2026 card structure uses <section class="propety"> with:
        - .propetyTitle a  -> title + detail URL
        - dl.price dd      -> price
        - dt/dd pairs      -> property details (area, floor plan, address, etc.)
        - .imageOuter img  -> thumbnail image
        """

        # ----- Detail-page URL -----
        link_el = (
            card.select_one("a[href*='/bukken/detail/buy/']")
            or card.select_one("a[href*='/buy/detail/']")
            or card.select_one(".propetyTitle a")
            or card.select_one("a.sp")
            or card.select_one("a[href]")
        )
        if not link_el:
            return None

        href = link_el.get("href", "")
        if isinstance(href, list):
            href = href[0]
        if not href:
            return None
        if href.startswith("//"):
            href = "https:" + href
        elif not href.startswith("http"):
            href = urljoin(self.base_url, href)

        source_id = _extract_source_id(href)

        # ----- Title -----
        title: str | None = None
        title_el = card.select_one(".propetyTitle a") or card.select_one(".propetyTitle")
        if title_el:
            t = title_el.get_text(strip=True)
            if t and len(t) > 2:
                title = t
        if not title:
            for sel in ["h2", "h3", ".property-title", ".item-title",
                         "[class*='title']", "a"]:
                el = card.select_one(sel)
                if el:
                    t = el.get_text(strip=True)
                    if t and len(t) > 2:
                        title = t
                        break

        # ----- Price -----
        price: int | None = None
        # 2026 layout: <dl class="price"><dd><span>430</span>万円</dd>
        price_el = card.select_one("dl.price dd")
        if price_el:
            price = _parse_price(price_el.get_text(strip=True))
        if price is None:
            for sel in [".price", "[class*='price']", ".kakaku",
                        "[class*='kakaku']", "span.value", ".property-price"]:
                el = card.select_one(sel)
                if el:
                    price = _parse_price(el.get_text(strip=True))
                    if price is not None:
                        break
        # Fallback: search full card text for price patterns
        if price is None:
            card_text = card.get_text()
            price = _parse_price(card_text)

        # ----- Raw key/value data from dt/dd lists -----
        raw_data = self._extract_raw_data(card)

        # ----- Address -----
        address: str | None = raw_data.get("所在地") or raw_data.get("住所")
        if not address:
            for sel in [".address", "[class*='address']", "[class*='location']",
                        ".area", "[class*='area']"]:
                el = card.select_one(sel)
                if el:
                    t = el.get_text(strip=True)
                    if re.search(r"[都道府県市区町村郡]", t):
                        address = t
                        break
        # Fallback: scan all text nodes for something that looks like an address
        if not address:
            for el in card.find_all(["span", "p", "div", "dd", "td"]):
                t = el.get_text(strip=True)
                if re.search(r"[都道府県].*[市区町村郡]", t) and len(t) < 100:
                    address = t
                    break

        # ----- Land / building area -----
        land_area: float | None = None
        building_area: float | None = None
        for key, value in raw_data.items():
            if any(k in key for k in ("土地", "敷地")):
                land_area = land_area or _parse_area(value)
            if any(k in key for k in ("建物", "延床", "延べ床", "専有")):
                building_area = building_area or _parse_area(value)
        # If not found in structured data, try searching card text
        if land_area is None or building_area is None:
            for el in card.find_all(["span", "p", "div", "dd", "td"]):
                t = el.get_text(strip=True)
                if land_area is None and re.search(r"土地|敷地", t):
                    land_area = _parse_area(t)
                if building_area is None and re.search(r"建物|延床|延べ床|専有", t):
                    building_area = _parse_area(t)

        # ----- Floor plan (間取り) -----
        floor_plan: str | None = raw_data.get("間取り") or raw_data.get("間取")
        if not floor_plan:
            plan_match = re.search(
                r"\d+\s*[SLDK]+(?:\s*[+＋]\s*S)?",
                card.get_text(),
            )
            if plan_match:
                floor_plan = plan_match.group(0).strip()

        # ----- Year built -----
        year_built: int | None = None
        for key, value in raw_data.items():
            if any(k in key for k in ("築年", "建築年", "完成")):
                year_built = _parse_year(value)
                if year_built:
                    break

        # ----- Images from card -----
        image_urls: list[str] = []
        for img in card.select("img"):
            src = img.get("data-src") or img.get("src")
            if isinstance(src, list):
                src = src[0]
            if src and isinstance(src, str):
                if src.startswith("//"):
                    src = "https:" + src
                elif not src.startswith("http"):
                    src = urljoin(self.base_url, src)
                if any(skip in src for skip in ("icon", "logo", "spacer", "blank", "noimage")):
                    continue
                if src not in image_urls:
                    image_urls.append(src)

        # ----- Prefecture / municipality from address -----
        prefecture: str | None = None
        municipality: str | None = None
        if address:
            prefecture = _prefecture_from_address(address)
            municipality = _municipality_from_address(address)
        if not prefecture and prefecture_code:
            prefecture = _PREFECTURE_NAMES.get(prefecture_code)

        # Must have at least a URL to be useful
        if not address and price is None and not title:
            return None

        return RawListing(
            source="akiya",
            source_id=source_id,
            source_url=href,
            title=title,
            price=price,
            address=address,
            prefecture=prefecture,
            municipality=municipality,
            land_area_sqm=land_area,
            building_area_sqm=building_area,
            floor_plan=floor_plan,
            year_built=year_built,
            image_urls=image_urls[:20],
            raw_data=raw_data,
        )

    # ------------------------------------------------------------------
    # Structured data extraction from card
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_raw_data(card: Tag) -> dict[str, str]:
        """Extract key/value pairs from th/td and dt/dd structures."""
        raw: dict[str, str] = {}

        # th/td pairs
        for row in card.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(strip=True)
                if key and val:
                    raw[key] = val

        # dt/dd pairs
        for dt in card.select("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                key = dt.get_text(strip=True)
                val = dd.get_text(strip=True)
                if key and val:
                    raw[key] = val

        # If no structured data, grab labelled spans
        if not raw:
            for i, cell in enumerate(
                card.select("td, dd, span, p, div.value, [class*='value']")
            ):
                text = cell.get_text(strip=True)
                if text and len(text) > 1:
                    raw[f"field_{i}"] = text

        return raw

    # ------------------------------------------------------------------
    # scrape_detail
    # ------------------------------------------------------------------

    async def scrape_detail(self, listing_url: str) -> RawListing | None:
        """Scrape a single akiya bank detail page.

        Fetches the HTML with ``httpx`` and parses the property details
        tables with BeautifulSoup.
        """
        logger.info("Scraping akiya detail page", url=listing_url)

        async with httpx.AsyncClient(
            headers=_DEFAULT_HEADERS,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        ) as client:
            try:
                response = await client.get(listing_url)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "HTTP error on detail page",
                    status=exc.response.status_code,
                    url=listing_url,
                )
                return None
            except httpx.RequestError as exc:
                logger.error(
                    "Request error on detail page",
                    url=listing_url,
                    error=str(exc),
                )
                return None

        html = response.text
        return self._parse_detail_page(html, listing_url)

    # ------------------------------------------------------------------
    # Detail page parsing
    # ------------------------------------------------------------------

    def _parse_detail_page(self, html: str, url: str) -> RawListing | None:
        """Parse a full akiya detail page into a RawListing."""
        soup = BeautifulSoup(html, "html.parser")

        # ---- Collect all key-value pairs from tables and definition lists ----
        details: dict[str, str] = {}

        for row in soup.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(strip=True)
                if key and val:
                    details[key] = val

        for dt in soup.select("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                key = dt.get_text(strip=True)
                val = dd.get_text(strip=True)
                if key and val:
                    details[key] = val

        # ---- Title ----
        title: str | None = None
        for selector in ["h1", "h2", ".property-title", "[class*='heading']",
                         "[class*='title']"]:
            el = soup.select_one(selector)
            if el:
                t = el.get_text(strip=True)
                if t and len(t) > 2:
                    title = t
                    break

        # ---- Price ----
        price: int | None = None
        for key in ("販売価格", "価格", "物件価格", "希望価格", "譲渡価格",
                     "売却価格", "金額"):
            if key in details:
                price = _parse_price(details[key])
                if price is not None:
                    break
        # Fallback: class-based price element
        if price is None:
            for sel in [".price", "[class*='price']", ".kakaku",
                        ".price-red-strong"]:
                el = soup.select_one(sel)
                if el:
                    price = _parse_price(el.get_text(strip=True))
                    if price is not None:
                        break

        # ---- Address ----
        address: str | None = None
        for key in ("所在地", "住所", "物件所在地", "所在"):
            if key in details:
                address = details[key]
                break
        # Fuzzy match: detail pages may have keys like "所在地周辺情報を調べる"
        if not address:
            for detail_key, val in details.items():
                if detail_key.startswith("所在地") or detail_key.startswith("住所"):
                    # Clean: strip trailing "周辺情報を調べる" etc from value too
                    clean = re.sub(r"周辺情報.*$", "", val).strip()
                    if clean and re.search(r"[都道府県]", clean):
                        address = clean
                        break

        # ---- Areas ----
        land_area: float | None = None
        building_area: float | None = None
        for key in ("土地面積", "敷地面積", "土地"):
            if key in details:
                land_area = _parse_area(details[key])
                if land_area is not None:
                    break
        for key in ("建物面積", "延床面積", "延べ床面積", "専有面積", "建物"):
            if key in details:
                building_area = _parse_area(details[key])
                if building_area is not None:
                    break

        # ---- Year built ----
        year_built: int | None = None
        for key in ("築年月", "建築年月", "建築年", "完成時期", "築年数", "建築時期"):
            if key in details:
                year_built = _parse_year(details[key])
                if year_built is not None:
                    break

        # ---- Structure ----
        structure: str | None = None
        for key in ("構造", "建物構造", "構造・工法"):
            if key in details:
                structure = details[key]
                break

        # ---- Floor plan ----
        floor_plan: str | None = None
        for key in ("間取り", "間取"):
            if key in details:
                floor_plan = details[key]
                break

        # ---- Floors ----
        floors: int | None = None
        for key in ("階数", "階建"):
            if key in details:
                m = re.search(r"(\d+)", details[key])
                if m:
                    floors = int(m.group(1))
                    break

        # ---- Road info ----
        road_width: float | None = None
        road_frontage: float | None = None
        for key in ("前面道路幅員", "前面道路", "道路幅員", "接道状況"):
            if key in details:
                road_width = _parse_float(details[key])
                if road_width is not None:
                    break
        for key in ("接道間口", "間口"):
            if key in details:
                road_frontage = _parse_float(details[key])
                if road_frontage is not None:
                    break

        # ---- Zoning / planning ----
        city_planning_zone: str | None = None
        for key in ("都市計画", "都市計画区域"):
            if key in details:
                city_planning_zone = details[key]
                break

        use_zone: str | None = None
        if "用途地域" in details:
            use_zone = details["用途地域"]

        coverage_ratio: float | None = None
        for key in ("建ぺい率", "建蔽率"):
            if key in details:
                coverage_ratio = _parse_float(details[key])
                if coverage_ratio is not None:
                    break

        floor_area_ratio: float | None = None
        if "容積率" in details:
            floor_area_ratio = _parse_float(details["容積率"])

        # ---- Rebuild status ----
        rebuild_possible: bool | None = None
        for key in ("備考", "条件", "その他", "再建築", "特記事項",
                     "物件の特徴", "補足"):
            if key in details:
                text = details[key]
                if "再建築不可" in text:
                    rebuild_possible = False
                elif "再建築可" in text:
                    rebuild_possible = True

        # ---- Geo-coordinates (if embedded in the page) ----
        latitude: float | None = None
        longitude: float | None = None

        # Try to find coordinates in a script tag (Google Maps embed etc.)
        for script in soup.select("script"):
            script_text = script.string or ""
            lat_match = re.search(r"lat(?:itude)?[\"':\s]+(-?\d+\.\d+)", script_text)
            lng_match = re.search(r"(?:lng|lon(?:gitude)?)[\"':\s]+(-?\d+\.\d+)", script_text)
            if lat_match and lng_match:
                latitude = float(lat_match.group(1))
                longitude = float(lng_match.group(1))
                break

        # Also check for a Google Maps iframe src
        if latitude is None:
            iframe = soup.select_one("iframe[src*='maps.google'], iframe[src*='google.com/maps']")
            if iframe:
                src = iframe.get("src", "")
                if isinstance(src, list):
                    src = src[0]
                coord_match = re.search(r"q=(-?\d+\.\d+),\s*(-?\d+\.\d+)", src)
                if coord_match:
                    latitude = float(coord_match.group(1))
                    longitude = float(coord_match.group(2))

        # ---- Images ----
        image_urls: list[str] = []

        # 2026: images may be in a JavaScript variable (carousel data)
        for script in soup.select("script"):
            script_text = script.string or ""
            img_match = re.search(
                r'image_tile_carousel_image_s\s*=\s*(\[.*?\])',
                script_text,
                re.DOTALL,
            )
            if img_match:
                try:
                    img_data = json.loads(img_match.group(1))
                    for item in img_data:
                        if isinstance(item, dict):
                            full_url = (
                                item.get("image_url_fullsize")
                                or item.get("image_url_thumbnail")
                            )
                            if full_url:
                                if full_url.startswith("//"):
                                    full_url = "https:" + full_url
                                if full_url not in image_urls:
                                    image_urls.append(full_url)
                except (json.JSONDecodeError, TypeError):
                    pass

        # Fallback: img tags with relevant src patterns
        if not image_urls:
            for img in soup.select(
                "img[src*='akiya'], img[src*='property'], img[src*='photo'], "
                "img[src*='image'], img[src*='bukken'], img[data-src]"
            ):
                src = img.get("data-src") or img.get("src")
                if isinstance(src, list):
                    src = src[0]
                if src and isinstance(src, str):
                    if src.startswith("//"):
                        src = "https:" + src
                    elif not src.startswith("http"):
                        src = urljoin(self.base_url, src)
                    # Skip tiny icons / spacer images
                    if any(skip in src for skip in ("icon", "logo", "spacer", "blank", "noimage")):
                        continue
                    if src not in image_urls:
                        image_urls.append(src)

        # Fallback: grab all reasonably-sized images
        if not image_urls:
            for img in soup.select("img[src]"):
                src = img.get("src", "")
                if isinstance(src, list):
                    src = src[0]
                if not isinstance(src, str):
                    continue
                # Filter out navigation/icon images by dimension attrs
                width = img.get("width", "999")
                if isinstance(width, str) and width.isdigit() and int(width) < 50:
                    continue
                if src.startswith("//"):
                    src = "https:" + src
                elif not src.startswith("http"):
                    src = urljoin(self.base_url, src)
                if any(skip in src for skip in ("icon", "logo", "spacer", "blank", "noimage")):
                    continue
                if src not in image_urls:
                    image_urls.append(src)

        # ---- Prefecture / municipality ----
        prefecture: str | None = None
        municipality: str | None = None
        if address:
            prefecture = _prefecture_from_address(address)
            municipality = _municipality_from_address(address)

        source_id = _extract_source_id(url)

        return RawListing(
            source="akiya",
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
            image_urls=image_urls[:20],
            raw_data=details,
        )
