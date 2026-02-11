"""
Japanese address normalization utilities for deduplication.

Handles:
- Full-width / half-width character conversion
- Kanji numeral to Arabic conversion
- Chome/ban/go normalization
- Common abbreviation expansion
"""

import re
import unicodedata


# Kanji numeral mapping
KANJI_NUMS = {
    "〇": "0", "一": "1", "二": "2", "三": "3", "四": "4",
    "五": "5", "六": "6", "七": "7", "八": "8", "九": "9",
    "十": "10", "百": "100", "千": "1000",
}

# Common address component patterns
CHOME_PATTERN = re.compile(r"(\d+)丁目")
BAN_PATTERN = re.compile(r"(\d+)番地?")
GO_PATTERN = re.compile(r"(\d+)号")


def normalize_width(text: str) -> str:
    """Convert full-width characters to half-width."""
    return unicodedata.normalize("NFKC", text)


def kanji_to_arabic(text: str) -> str:
    """Convert simple kanji numerals to Arabic. Handles 一~九, 十, 百, 千."""
    result = text

    # Handle compound numbers like 二十三 -> 23
    # Pattern: [千百十] preceded/followed by digits
    def replace_compound(match: re.Match) -> str:
        s = match.group(0)
        total = 0
        current = 0

        for char in s:
            if char in KANJI_NUMS:
                val = KANJI_NUMS[char]
                if val in ("10", "100", "1000"):
                    multiplier = int(val)
                    if current == 0:
                        current = 1
                    total += current * multiplier
                    current = 0
                else:
                    current = int(val)
            else:
                break

        total += current
        return str(total) if total > 0 else s

    # Match sequences of kanji numerals
    kanji_num_pattern = re.compile(r"[〇一二三四五六七八九十百千]+")
    result = kanji_num_pattern.sub(replace_compound, result)

    return result


def normalize_address(address: str) -> str:
    """
    Normalize a Japanese address for deduplication matching.

    Steps:
    1. Full-width to half-width
    2. Strip whitespace
    3. Kanji numerals to Arabic
    4. Normalize chome/ban/go to standard format
    5. Remove building names (after last 号)
    """
    if not address:
        return ""

    # Step 1: Width normalization
    text = normalize_width(address)

    # Step 2: Strip various whitespace
    text = re.sub(r"\s+", "", text)

    # Step 3: Kanji to Arabic
    text = kanji_to_arabic(text)

    # Step 4: Normalize separators
    # Convert "1丁目2番3号" pattern to "1-2-3" standard form
    text = re.sub(r"(\d+)丁目(\d+)番地?(\d+)号?", r"\1-\2-\3", text)
    text = re.sub(r"(\d+)丁目(\d+)番地?", r"\1-\2", text)
    text = re.sub(r"(\d+)丁目", r"\1丁目", text)

    # Normalize dash variants
    text = text.replace("ー", "-").replace("‐", "-").replace("−", "-").replace("―", "-")

    # Step 5: Remove building name (heuristic: after the last number group)
    # Keep everything up to and including the last number
    parts = re.split(r"(?<=\d)(?=[^\d\-])", text, maxsplit=0)
    if len(parts) > 1:
        # Keep only the address part (numbers and their context)
        # Find the last digit and keep up to there
        last_digit_pos = -1
        for i, c in enumerate(text):
            if c.isdigit():
                last_digit_pos = i
        if last_digit_pos >= 0:
            text = text[: last_digit_pos + 1]

    return text.strip()


def extract_prefecture(address: str) -> str | None:
    """Extract prefecture name from address."""
    prefectures_pattern = re.compile(
        r"^(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|"
        r"茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|"
        r"新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|"
        r"静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|"
        r"奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|"
        r"徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|"
        r"熊本県|大分県|宮崎県|鹿児島県|沖縄県)"
    )
    match = prefectures_pattern.match(address)
    return match.group(1) if match else None
