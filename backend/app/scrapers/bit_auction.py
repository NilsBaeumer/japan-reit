"""BIT (Broadcast Information of Tri-set system) court-auction scraper.

BIT is the official Japanese court-auction information portal
(https://www.bit.courts.go.jp).  Auction listings include property details
published as HTML pages *and* supplementary PDF documents (the so-called
3-set: 物件明細書, 現況調査報告書, 評価書).  Full extraction therefore
requires both HTML scraping and PDF parsing.

This scraper uses httpx + BeautifulSoup (server-rendered HTML with
form-based search).  Crawl delay is set conservatively (8 s) because this
is a government site.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

import httpx
import structlog
from bs4 import BeautifulSoup, Tag

from app.scrapers.base import AbstractScraper, RawListing, SearchParams
from app.scrapers.registry import register_scraper

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Prefecture code -> BIT court-district code mapping
#
# BIT groups courts by High Court jurisdiction (札幌, 仙台, 東京, 名古屋,
# 大阪, 広島, 高松, 福岡).  Each standard JIS prefecture code (01-47) maps
# to the corresponding High Court district used in BIT search URLs.
# ---------------------------------------------------------------------------

COURT_DISTRICT_MAP: dict[str, str] = {
    # Hokkaido -> Sapporo High Court
    "01": "sapporo",
    # Tohoku -> Sendai High Court
    "02": "sendai",
    "03": "sendai",
    "04": "sendai",
    "05": "sendai",
    "06": "sendai",
    "07": "sendai",
    # Kanto -> Tokyo High Court
    "08": "tokyo",
    "09": "tokyo",
    "10": "tokyo",
    "11": "tokyo",
    "12": "tokyo",
    "13": "tokyo",
    "14": "yokohama",
    # Chubu / Hokuriku -> Nagoya High Court (+ Tokyo for some)
    "15": "tokyo",   # Niigata -> Tokyo High Court jurisdiction
    "16": "nagoya",  # Toyama
    "17": "nagoya",  # Ishikawa (Kanazawa)
    "18": "nagoya",  # Fukui
    "19": "tokyo",   # Yamanashi
    "20": "tokyo",   # Nagano
    "21": "nagoya",  # Gifu
    "22": "nagoya",  # Shizuoka
    "23": "nagoya",  # Aichi
    # Kinki -> Osaka High Court
    "24": "nagoya",  # Mie -> Nagoya High Court
    "25": "osaka",   # Shiga
    "26": "osaka",   # Kyoto
    "27": "osaka",   # Osaka
    "28": "kobe",    # Hyogo
    "29": "osaka",   # Nara
    "30": "osaka",   # Wakayama
    # Chugoku -> Hiroshima High Court
    "31": "hiroshima",  # Tottori
    "32": "hiroshima",  # Shimane
    "33": "hiroshima",  # Okayama
    "34": "hiroshima",  # Hiroshima
    "35": "hiroshima",  # Yamaguchi
    # Shikoku -> Takamatsu High Court
    "36": "takamatsu",  # Tokushima
    "37": "takamatsu",  # Kagawa
    "38": "takamatsu",  # Ehime
    "39": "takamatsu",  # Kochi
    # Kyushu / Okinawa -> Fukuoka High Court
    "40": "fukuoka",  # Fukuoka
    "41": "fukuoka",  # Saga
    "42": "fukuoka",  # Nagasaki
    "43": "fukuoka",  # Kumamoto
    "44": "fukuoka",  # Oita
    "45": "fukuoka",  # Miyazaki
    "46": "fukuoka",  # Kagoshima
    "47": "fukuoka",  # Okinawa (Naha)
}

# BIT property type codes used in the search form.
PROPERTY_TYPE_MAP: dict[str, str] = {
    "detached_house": "10",  # 土地付建物 (land + building)
    "land": "20",            # 土地 (land only)
    "condo": "30",           # マンション (condominium)
    "other": "99",           # その他
}

# User-Agent for polite crawling
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Helper: price parsing for auction-specific formats
# ---------------------------------------------------------------------------

def _parse_auction_price(text: str) -> int | None:
    """Parse a Japanese auction price string into integer yen.

    Handles formats commonly seen on BIT:
      - ``1,500,000円``  / ``1500000円``
      - ``150万円``  / ``1,500万円``
      - ``1億5000万円`` / ``1億円``
      - Plain digits ``1500000``
    """
    if not text:
        return None

    text = text.replace(",", "").replace("，", "").replace(" ", "").replace("\u3000", "")

    # Pattern: N億M万円
    m = re.search(r"(\d+)億(?:(\d+)万)?円?", text)
    if m:
        total = int(m.group(1)) * 100_000_000
        if m.group(2):
            total += int(m.group(2)) * 10_000
        return total

    # Pattern: N万円
    m = re.search(r"(\d+)万円?", text)
    if m:
        return int(m.group(1)) * 10_000

    # Pattern: plain digits followed by 円
    m = re.search(r"(\d{4,})円", text)
    if m:
        return int(m.group(1))

    # Pattern: plain digits only (no currency marker)
    m = re.search(r"(\d{4,})", text)
    if m:
        return int(m.group(1))

    return None


def _parse_area(text: str) -> float | None:
    """Parse area from text like ``100.5m²``, ``100.5㎡``, ``100.5平米``."""
    if not text:
        return None
    text = text.replace(",", "")
    m = re.search(r"([\d.]+)\s*(?:m[²2]|㎡|平米|平方メートル)", text)
    return float(m.group(1)) if m else None


def _parse_year(text: str) -> int | None:
    """Parse construction year from Japanese text (西暦 and 和暦).

    Handles:
      - ``2005年`` (Western)
      - ``平成17年`` / ``令和5年`` / ``昭和60年`` (Japanese era)
    """
    if not text:
        return None

    # Western year
    m = re.search(r"(\d{4})年", text)
    if m:
        year = int(m.group(1))
        if 1868 <= year <= 2100:
            return year

    # Japanese era
    era_base = {
        "令和": 2018,
        "平成": 1988,
        "昭和": 1925,
        "大正": 1911,
        "明治": 1867,
    }
    for era, base in era_base.items():
        m = re.search(rf"{era}(\d+)年", text)
        if m:
            return base + int(m.group(1))

    return None


def _parse_float(text: str) -> float | None:
    """Extract first decimal number from *text*."""
    if not text:
        return None
    m = re.search(r"([\d.]+)", text.replace(",", ""))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _extract_prefecture_municipality(address: str) -> tuple[str | None, str | None]:
    """Split a Japanese address into (prefecture, municipality).

    Returns (prefecture, municipality) or (None, None) when parsing fails.
    """
    if not address:
        return None, None

    # Match prefecture (都道府県)
    m = re.match(
        r"((?:東京都|北海道|(?:京都|大阪)府|.{2,3}県))"
        r"((?:[^市区町村郡]+?[市区町村郡](?:[^市区町村]+?[市区町村])?))?",
        address,
    )
    if m:
        return m.group(1), m.group(2)

    return None, None


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


@register_scraper("bit")
class BitAuctionScraper(AbstractScraper):
    """Scraper for BIT court-auction (bit.courts.go.jp) listings.

    BIT is a government-run site with server-rendered HTML.  The scraper
    uses ``httpx.AsyncClient`` for HTTP requests and ``BeautifulSoup`` for
    HTML parsing.  No browser automation is required.

    Key characteristics:
    - Form-based search (POST or GET with query parameters)
    - Results displayed in HTML tables
    - Detail pages link to 3-set PDF documents
    - Conservative 8-second crawl delay (government site)
    """

    source_id = "bit"
    base_url = "https://www.bit.courts.go.jp"
    crawl_delay_seconds = 8.0

    # ------------------------------------------------------------------
    # URL / request building
    # ------------------------------------------------------------------

    def _build_search_url(self, params: SearchParams, page: int = 1) -> str:
        """Build the BIT property search URL for a given page.

        The BIT search endpoint accepts GET parameters.  The URL pattern is:
        ``/app/list/pt001/h01`` with query parameters for property type,
        court district, price range, and pagination.
        """
        base_search = f"{self.base_url}/app/list/pt001/h01"

        query_parts: list[str] = []

        # Property type
        prop_code = PROPERTY_TYPE_MAP.get(params.property_type, "10")
        query_parts.append(f"bpiKubun={prop_code}")

        # Court district (derived from prefecture code)
        if params.prefecture_code:
            district = COURT_DISTRICT_MAP.get(params.prefecture_code)
            if district:
                query_parts.append(f"courtAreaId={district}")
            # Also pass the prefecture code for sub-filtering
            query_parts.append(f"kenCode={params.prefecture_code}")

        # Price range (BIT expects yen values)
        if params.price_min is not None:
            query_parts.append(f"priceFrom={params.price_min}")
        if params.price_max is not None:
            query_parts.append(f"priceTo={params.price_max}")

        # Pagination
        query_parts.append(f"page={page}")

        # Sort by newest
        query_parts.append("sort=new")

        return f"{base_search}?{'&'.join(query_parts)}"

    def _build_search_form_data(self, params: SearchParams, page: int = 1) -> dict[str, str]:
        """Build POST form data for the BIT search form.

        Some BIT search flows use POST-based form submission.  This method
        builds the form payload as an alternative to URL-based search.
        """
        prop_code = PROPERTY_TYPE_MAP.get(params.property_type, "10")
        form_data: dict[str, str] = {
            "bpiKubun": prop_code,
            "page": str(page),
            "sort": "new",
        }

        if params.prefecture_code:
            district = COURT_DISTRICT_MAP.get(params.prefecture_code)
            if district:
                form_data["courtAreaId"] = district
            form_data["kenCode"] = params.prefecture_code

        if params.price_min is not None:
            form_data["priceFrom"] = str(params.price_min)
        if params.price_max is not None:
            form_data["priceTo"] = str(params.price_max)

        return form_data

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_listings(self, params: SearchParams) -> list[RawListing]:
        """Search BIT for court-auction lots matching *params*.

        Iterates through paginated search results, parsing each page with
        BeautifulSoup.  Respects the configured crawl delay between pages.
        """
        all_listings: list[RawListing] = []

        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en;q=0.5",
            "Referer": self.base_url,
        }

        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        ) as client:
            for page_num in range(1, params.max_pages + 1):
                url = self._build_search_url(params, page_num)
                logger.info(
                    "bit_auction.search_page",
                    page=page_num,
                    url=url,
                )

                try:
                    # Try GET first; fall back to POST if needed
                    resp = await client.get(url)

                    if resp.status_code == 405:
                        # Server prefers POST
                        form_data = self._build_search_form_data(params, page_num)
                        resp = await client.post(
                            f"{self.base_url}/app/list/pt001/h01",
                            data=form_data,
                        )

                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    logger.error(
                        "bit_auction.search_http_error",
                        page=page_num,
                        status=exc.response.status_code,
                    )
                    break
                except httpx.RequestError as exc:
                    logger.error(
                        "bit_auction.search_request_error",
                        page=page_num,
                        error=str(exc),
                    )
                    break

                page_listings = self._parse_search_results(resp.text)

                if not page_listings:
                    logger.info("bit_auction.no_more_results", page=page_num)
                    break

                all_listings.extend(page_listings)
                logger.info(
                    "bit_auction.page_parsed",
                    page=page_num,
                    count=len(page_listings),
                    total=len(all_listings),
                )

                # Check for next-page link before sleeping
                if not self._has_next_page(resp.text):
                    logger.info("bit_auction.last_page", page=page_num)
                    break

                # Respect crawl delay between pages
                if page_num < params.max_pages:
                    await self._delay()

        logger.info(
            "bit_auction.search_complete",
            total_listings=len(all_listings),
        )
        return all_listings

    # ------------------------------------------------------------------
    # Search-result parsing
    # ------------------------------------------------------------------

    def _parse_search_results(self, html: str) -> list[RawListing]:
        """Parse a BIT search results page and return a list of ``RawListing``.

        BIT displays auction lots in an HTML table.  Each row typically
        contains: case number, court name, property type, address,
        minimum bid price (売却基準価額), sale schedule, and a link to
        the detail page.
        """
        soup = BeautifulSoup(html, "html.parser")
        listings: list[RawListing] = []

        # Strategy 1: look for the results table by class/id
        result_rows = (
            soup.select("table.result-table tbody tr")
            or soup.select("table.list-table tbody tr")
            or soup.select("div.result-list table tr")
            or soup.select("#result-list table tr")
        )

        # Strategy 2: broader search -- any table row with a link to detail
        if not result_rows:
            result_rows = []
            for a_tag in soup.select("a[href*='pt001'], a[href*='detail']"):
                row = a_tag.find_parent("tr")
                if row and row not in result_rows:
                    result_rows.append(row)

        # Strategy 3: card-style layout (div-based)
        if not result_rows:
            cards = (
                soup.select("div.property-item")
                or soup.select("div.result-item")
                or soup.select("div.list-item")
            )
            for card in cards:
                try:
                    listing = self._parse_card(card)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.warning("bit_auction.card_parse_error", error=str(e))
            return listings

        # Parse table rows
        for row in result_rows:
            try:
                listing = self._parse_row(row)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.warning("bit_auction.row_parse_error", error=str(e))

        return listings

    def _parse_row(self, row: Tag) -> RawListing | None:
        """Extract listing data from a single search-result table row.

        Expected columns (order may vary):
        - Case number (事件番号)
        - Court name (裁判所)
        - Property type (種別)
        - Address (所在地)
        - Minimum bid price (売却基準価額 / 買受可能価額)
        - Sale period (売却期間)
        - Detail link
        """
        cells = row.select("td")
        if not cells:
            return None

        # Gather all text content from the row for flexible parsing
        row_text = row.get_text(separator=" ", strip=True)
        raw_data: dict[str, Any] = {"row_text": row_text}

        # Find detail link
        detail_link_tag = (
            row.select_one("a[href*='pt001']")
            or row.select_one("a[href*='detail']")
            or row.select_one("a[href]")
        )
        detail_url = ""
        if detail_link_tag:
            href = detail_link_tag.get("href", "")
            if isinstance(href, list):
                href = href[0]
            detail_url = urljoin(self.base_url, str(href)) if href else ""

        # Extract source ID from the URL or case number
        source_id = ""
        if detail_url:
            # Try to extract ID from URL query/path
            id_match = re.search(r"[?&]id=([^&]+)", detail_url)
            if id_match:
                source_id = id_match.group(1)
            else:
                # Use the last path segment
                path_match = re.search(r"/([^/?]+)(?:\?|$)", detail_url.rstrip("/"))
                if path_match:
                    source_id = path_match.group(1)

        # Extract case number (事件番号) -- typically like "令和6年(ケ)第123号"
        case_number = ""
        case_match = re.search(
            r"(?:令和|平成|昭和)\d+年\s*[(（][^)）]+[)）]\s*第?\d+号",
            row_text,
        )
        if case_match:
            case_number = case_match.group(0)
            raw_data["case_number"] = case_number

        if not source_id and case_number:
            # Normalise the case number into a compact ID
            source_id = re.sub(r"\s+", "", case_number)

        if not source_id:
            # Last resort: hash of row text
            source_id = f"bit-{hash(row_text) & 0xFFFFFFFF:08x}"

        # Extract price -- look for yen amounts
        price: int | None = None
        for cell in cells:
            cell_text = cell.get_text(strip=True)
            if "円" in cell_text or re.search(r"[\d,]+", cell_text):
                parsed = _parse_auction_price(cell_text)
                if parsed and parsed >= 10_000:  # Auction prices are at least 万 range
                    price = parsed
                    raw_data["price_text"] = cell_text
                    break

        # Extract address -- look for cell containing prefecture/address markers
        address: str | None = None
        for cell in cells:
            cell_text = cell.get_text(strip=True)
            if re.search(r"[都道府県市区町村郡]", cell_text) and len(cell_text) > 4:
                address = cell_text
                raw_data["address_text"] = cell_text
                break

        # Extract court name
        court_name = ""
        for cell in cells:
            cell_text = cell.get_text(strip=True)
            if "裁判所" in cell_text or "地裁" in cell_text or "支部" in cell_text:
                court_name = cell_text
                raw_data["court_name"] = court_name
                break

        # Extract sale schedule
        for cell in cells:
            cell_text = cell.get_text(strip=True)
            date_match = re.search(
                r"(?:令和|平成)?\d+年\d+月\d+日", cell_text
            )
            if date_match:
                raw_data["sale_date"] = date_match.group(0)
                break

        # Derive prefecture / municipality from address
        prefecture, municipality = _extract_prefecture_municipality(address or "")

        # Build title from available info
        title_parts: list[str] = []
        if court_name:
            title_parts.append(court_name)
        if case_number:
            title_parts.append(case_number)
        if address:
            title_parts.append(address)
        title = " ".join(title_parts) if title_parts else row_text[:80]

        # Must have at least a detail URL or an address to be useful
        if not detail_url and not address:
            return None

        return RawListing(
            source="bit",
            source_id=source_id,
            source_url=detail_url,
            title=title,
            price=price,
            address=address,
            prefecture=prefecture,
            municipality=municipality,
            raw_data=raw_data,
        )

    def _parse_card(self, card: Tag) -> RawListing | None:
        """Parse a card-style (div-based) search result into a ``RawListing``."""
        card_text = card.get_text(separator=" ", strip=True)
        raw_data: dict[str, Any] = {"card_text": card_text}

        # Detail link
        link_tag = (
            card.select_one("a[href*='pt001']")
            or card.select_one("a[href*='detail']")
            or card.select_one("a[href]")
        )
        detail_url = ""
        if link_tag:
            href = link_tag.get("href", "")
            if isinstance(href, list):
                href = href[0]
            detail_url = urljoin(self.base_url, str(href)) if href else ""

        source_id = ""
        if detail_url:
            id_match = re.search(r"[?&]id=([^&]+)", detail_url)
            if id_match:
                source_id = id_match.group(1)
            else:
                path_match = re.search(r"/([^/?]+)(?:\?|$)", detail_url.rstrip("/"))
                if path_match:
                    source_id = path_match.group(1)
        if not source_id:
            source_id = f"bit-{hash(card_text) & 0xFFFFFFFF:08x}"

        # Price
        price = _parse_auction_price(card_text)

        # Address
        address: str | None = None
        addr_match = re.search(
            r"((?:東京都|北海道|(?:京都|大阪)府|.{2,3}県).+?(?:[市区町村郡].+?))\s",
            card_text,
        )
        if addr_match:
            address = addr_match.group(1).strip()

        prefecture, municipality = _extract_prefecture_municipality(address or "")

        if not detail_url and not address:
            return None

        return RawListing(
            source="bit",
            source_id=source_id,
            source_url=detail_url,
            title=card_text[:120],
            price=price,
            address=address,
            prefecture=prefecture,
            municipality=municipality,
            raw_data=raw_data,
        )

    def _has_next_page(self, html: str) -> bool:
        """Return ``True`` if the search results page has a next-page link."""
        soup = BeautifulSoup(html, "html.parser")

        # Look for a "次へ" (next) link or similar pagination controls
        for a_tag in soup.select("a"):
            link_text = a_tag.get_text(strip=True)
            if link_text in ("次へ", "次のページ", "次ページ", ">", ">>"):
                return True

        # Look for pagination nav with rel="next"
        if soup.select_one("a[rel='next']"):
            return True

        # Look for numbered pagination where current page is not the last
        page_links = soup.select("ul.pagination li a, div.pager a, nav.pagination a")
        if page_links:
            current = soup.select_one(
                "ul.pagination li.active, div.pager .current, nav.pagination .current"
            )
            if current:
                # If there are links after the current page marker
                current_parent = current.find_parent(["li", "span", "div"])
                if current_parent:
                    next_sibling = current_parent.find_next_sibling()
                    if next_sibling and next_sibling.select_one("a"):
                        return True

        return False

    # ------------------------------------------------------------------
    # Detail page
    # ------------------------------------------------------------------

    async def scrape_detail(self, listing_url: str) -> RawListing | None:
        """Scrape a single BIT auction-lot detail page.

        Fetches the detail HTML and extracts property metadata including:
        - Minimum bid price (売却基準価額) and purchasable price (買受可能価額)
        - Location / address
        - Land area, building area
        - Property structure, year built
        - Zoning information
        - Links to 3-set PDF documents
        - Images

        PDF parsing is stubbed out; the PDF URLs are recorded in ``raw_data``
        for future implementation.
        """
        if not listing_url:
            return None

        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en;q=0.5",
            "Referer": self.base_url,
        }

        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        ) as client:
            try:
                resp = await client.get(listing_url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "bit_auction.detail_http_error",
                    url=listing_url,
                    status=exc.response.status_code,
                )
                return None
            except httpx.RequestError as exc:
                logger.warning(
                    "bit_auction.detail_request_error",
                    url=listing_url,
                    error=str(exc),
                )
                return None

        return self._parse_detail_page(resp.text, listing_url)

    def _parse_detail_page(self, html: str, url: str) -> RawListing | None:
        """Parse a BIT detail page into a ``RawListing``."""
        soup = BeautifulSoup(html, "html.parser")

        # ------------------------------------------------------------------
        # Collect all key-value pairs from <table> th/td and <dl> dt/dd
        # ------------------------------------------------------------------
        details: dict[str, str] = {}

        for row in soup.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                key = th.get_text(strip=True)
                value = td.get_text(strip=True)
                if key and value:
                    details[key] = value

        for dt_tag in soup.select("dt"):
            dd_tag = dt_tag.find_next_sibling("dd")
            if dd_tag:
                key = dt_tag.get_text(strip=True)
                value = dd_tag.get_text(strip=True)
                if key and value:
                    details[key] = value

        raw_data: dict[str, Any] = {"detail_fields": details}

        # ------------------------------------------------------------------
        # Source ID
        # ------------------------------------------------------------------
        source_id = ""
        id_match = re.search(r"[?&]id=([^&]+)", url)
        if id_match:
            source_id = id_match.group(1)
        else:
            path_match = re.search(r"/([^/?]+)(?:\?|$)", url.rstrip("/"))
            if path_match:
                source_id = path_match.group(1)
        if not source_id:
            source_id = f"bit-{hash(url) & 0xFFFFFFFF:08x}"

        # ------------------------------------------------------------------
        # Case number
        # ------------------------------------------------------------------
        page_text = soup.get_text(separator=" ", strip=True)
        case_match = re.search(
            r"(?:令和|平成|昭和)\d+年\s*[(（][^)）]+[)）]\s*第?\d+号",
            page_text,
        )
        if case_match:
            raw_data["case_number"] = case_match.group(0)

        # ------------------------------------------------------------------
        # Court name
        # ------------------------------------------------------------------
        court_name = ""
        for key in ("裁判所", "裁判所名", "管轄裁判所"):
            if key in details:
                court_name = details[key]
                break
        if not court_name:
            court_match = re.search(r"(.+?(?:地方裁判所|地裁|家裁).{0,10}?(?:支部)?)", page_text)
            if court_match:
                court_name = court_match.group(1).strip()
        if court_name:
            raw_data["court_name"] = court_name

        # ------------------------------------------------------------------
        # Price: 売却基準価額 / 買受可能価額
        # ------------------------------------------------------------------
        price: int | None = None
        for key in (
            "売却基準価額",
            "買受可能価額",
            "売却基準価格",
            "最低売却価額",
            "価格",
            "売却価額",
        ):
            if key in details:
                price = _parse_auction_price(details[key])
                raw_data["price_label"] = key
                raw_data["price_text"] = details[key]
                if price:
                    break

        # If no labelled price found, scan page text
        if price is None:
            price_match = re.search(
                r"(?:売却基準価額|買受可能価額)[^\d]*([\d,]+)\s*円",
                page_text,
            )
            if price_match:
                price = _parse_auction_price(price_match.group(1) + "円")

        # ------------------------------------------------------------------
        # Address
        # ------------------------------------------------------------------
        address: str | None = None
        for key in ("所在地", "所在", "物件所在地", "住所", "所在地住居表示"):
            if key in details:
                address = details[key]
                break

        prefecture, municipality = _extract_prefecture_municipality(address or "")

        # ------------------------------------------------------------------
        # Land area / Building area
        # ------------------------------------------------------------------
        land_area: float | None = None
        for key in ("土地面積", "地積", "土地"):
            if key in details:
                land_area = _parse_area(details[key])
                if land_area:
                    break

        building_area: float | None = None
        for key in ("建物面積", "床面積", "延床面積", "建物", "専有面積"):
            if key in details:
                building_area = _parse_area(details[key])
                if building_area:
                    break

        # ------------------------------------------------------------------
        # Floor plan
        # ------------------------------------------------------------------
        floor_plan: str | None = None
        for key in ("間取り", "間取"):
            if key in details:
                floor_plan = details[key]
                break
        if not floor_plan:
            plan_match = re.search(r"\d+[SLDK]+", page_text)
            if plan_match:
                floor_plan = plan_match.group(0)

        # ------------------------------------------------------------------
        # Year built
        # ------------------------------------------------------------------
        year_built: int | None = None
        for key in ("築年", "築年月", "建築年月", "建築年", "建築時期", "新築時期"):
            if key in details:
                year_built = _parse_year(details[key])
                if year_built:
                    break

        # ------------------------------------------------------------------
        # Structure
        # ------------------------------------------------------------------
        structure: str | None = None
        for key in ("構造", "建物構造", "構造・工法"):
            if key in details:
                structure = details[key]
                break

        # Floors
        floors: int | None = None
        for key in ("階数", "階建"):
            if key in details:
                floor_match = re.search(r"(\d+)", details[key])
                if floor_match:
                    floors = int(floor_match.group(1))
                    break

        # ------------------------------------------------------------------
        # Road info
        # ------------------------------------------------------------------
        road_width: float | None = None
        for key in ("前面道路", "前面道路幅員", "接道状況", "道路幅員"):
            if key in details:
                road_width = _parse_float(details[key])
                if road_width:
                    break

        road_frontage: float | None = None
        for key in ("接道間口", "間口"):
            if key in details:
                road_frontage = _parse_float(details[key])
                if road_frontage:
                    break

        # ------------------------------------------------------------------
        # Zoning
        # ------------------------------------------------------------------
        city_planning_zone = details.get("都市計画")
        use_zone = details.get("用途地域")

        coverage_ratio: float | None = None
        for key in ("建ぺい率", "建蔽率"):
            if key in details:
                coverage_ratio = _parse_float(details[key])
                if coverage_ratio:
                    break

        floor_area_ratio = _parse_float(details.get("容積率", ""))

        # ------------------------------------------------------------------
        # Rebuild possible?
        # ------------------------------------------------------------------
        rebuild_possible: bool | None = None
        full_text = " ".join(details.values()) + " " + page_text
        if "再建築不可" in full_text:
            rebuild_possible = False
        elif "再建築可" in full_text:
            rebuild_possible = True

        # ------------------------------------------------------------------
        # Images
        # ------------------------------------------------------------------
        image_urls: list[str] = []
        for img in soup.select("img"):
            src = img.get("data-src") or img.get("src")
            if not src or not isinstance(src, str):
                continue
            # Skip tiny icons / logos
            if any(skip in src.lower() for skip in ("icon", "logo", "spacer", "btn", "arrow")):
                continue
            full_url = urljoin(self.base_url, src)
            if full_url not in image_urls:
                image_urls.append(full_url)

        # ------------------------------------------------------------------
        # PDF document links (3-set)
        # ------------------------------------------------------------------
        pdf_urls: list[str] = []
        for a_tag in soup.select("a[href$='.pdf'], a[href*='.pdf']"):
            href = a_tag.get("href", "")
            if isinstance(href, list):
                href = href[0]
            if href:
                full_pdf_url = urljoin(self.base_url, str(href))
                label = a_tag.get_text(strip=True)
                pdf_urls.append(full_pdf_url)
                raw_data.setdefault("pdf_documents", []).append(
                    {"url": full_pdf_url, "label": label}
                )

        # Attempt stub PDF parsing (logs warning, returns empty dict)
        for pdf_info in raw_data.get("pdf_documents", []):
            pdf_data = self._parse_pdf(b"")  # stub -- no actual download
            if pdf_data:
                raw_data.setdefault("pdf_extracted", []).append(pdf_data)

        # ------------------------------------------------------------------
        # Title
        # ------------------------------------------------------------------
        title: str | None = None
        for selector in ("h1", "h2", ".property-title", ".detail-title", "title"):
            el = soup.select_one(selector)
            if el:
                candidate = el.get_text(strip=True)
                if candidate and len(candidate) > 3:
                    title = candidate
                    break
        if not title:
            parts = [court_name, raw_data.get("case_number", ""), address or ""]
            title = " ".join(p for p in parts if p)

        # ------------------------------------------------------------------
        # Coordinates (BIT pages rarely embed these, but check just in case)
        # ------------------------------------------------------------------
        latitude: float | None = None
        longitude: float | None = None

        # Look for embedded map coordinates in scripts
        for script in soup.select("script"):
            script_text = script.get_text()
            lat_match = re.search(r"lat[itude]*[\"':\s=]+([\d.]+)", script_text)
            lng_match = re.search(r"(?:lng|lon)[gitude]*[\"':\s=]+([\d.]+)", script_text)
            if lat_match and lng_match:
                try:
                    lat_val = float(lat_match.group(1))
                    lng_val = float(lng_match.group(1))
                    # Sanity check for Japan bounding box
                    if 24.0 <= lat_val <= 46.0 and 122.0 <= lng_val <= 154.0:
                        latitude = lat_val
                        longitude = lng_val
                except ValueError:
                    pass
                break

        return RawListing(
            source="bit",
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
            raw_data=raw_data,
        )

    # ------------------------------------------------------------------
    # PDF helpers
    # ------------------------------------------------------------------

    async def _download_pdf(self, pdf_url: str) -> bytes:
        """Download a PDF document from *pdf_url* using httpx.

        Returns the raw PDF bytes.  Respects crawl delay before the request.
        """
        await self._delay()

        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/pdf,*/*;q=0.8",
            "Referer": self.base_url,
        }

        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=httpx.Timeout(60.0),  # PDFs can be large
        ) as client:
            try:
                resp = await client.get(pdf_url)
                resp.raise_for_status()
                logger.info(
                    "bit_auction.pdf_downloaded",
                    url=pdf_url,
                    size_bytes=len(resp.content),
                )
                return resp.content
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "bit_auction.pdf_download_http_error",
                    url=pdf_url,
                    status=exc.response.status_code,
                )
                return b""
            except httpx.RequestError as exc:
                logger.warning(
                    "bit_auction.pdf_download_request_error",
                    url=pdf_url,
                    error=str(exc),
                )
                return b""

    def _parse_pdf(self, pdf_bytes: bytes) -> dict[str, Any]:
        """Extract structured data from a 3-set PDF document.

        This is a **stub** implementation.  PDF parsing requires additional
        dependencies (e.g. ``pdfplumber``, ``PyMuPDF``, or ``camelot``) and
        significant format-specific logic for the three document types:

        - 物件明細書 (property specification)
        - 現況調査報告書 (site inspection report)
        - 評価書 (appraisal report)

        Returns an empty dict and logs a warning so callers know that PDF
        extraction is not yet available.
        """
        if not pdf_bytes:
            return {}

        logger.warning(
            "bit_auction.pdf_parse_stub",
            message=(
                "PDF parsing is not yet implemented. "
                "Install pdfplumber or PyMuPDF and implement "
                "format-specific extraction for 3-set documents."
            ),
            size_bytes=len(pdf_bytes),
        )
        return {}
