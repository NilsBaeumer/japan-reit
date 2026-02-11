"""Tests for Japanese address normalization."""

from app.utils.japanese_address import (
    normalize_address,
    normalize_width,
    kanji_to_arabic,
    extract_prefecture,
)


class TestNormalizeWidth:
    def test_fullwidth_to_halfwidth(self):
        assert normalize_width("１２３") == "123"
        assert normalize_width("ＡＢＣ") == "ABC"


class TestKanjiToArabic:
    def test_simple_kanji(self):
        assert kanji_to_arabic("一") == "1"
        assert kanji_to_arabic("九") == "9"

    def test_compound_kanji(self):
        assert kanji_to_arabic("二十三") == "23"
        assert kanji_to_arabic("十") == "10"


class TestNormalizeAddress:
    def test_chome_ban_go(self):
        result = normalize_address("東京都新宿区西新宿1丁目2番3号")
        assert "1-2-3" in result

    def test_fullwidth_normalization(self):
        result = normalize_address("東京都新宿区西新宿１丁目２番３号")
        assert "1-2-3" in result

    def test_empty_string(self):
        assert normalize_address("") == ""

    def test_whitespace_removal(self):
        result = normalize_address("東京都 新宿区　西新宿")
        assert " " not in result
        assert "　" not in result


class TestExtractPrefecture:
    def test_tokyo(self):
        assert extract_prefecture("東京都新宿区西新宿") == "東京都"

    def test_osaka(self):
        assert extract_prefecture("大阪府大阪市北区") == "大阪府"

    def test_hokkaido(self):
        assert extract_prefecture("北海道札幌市中央区") == "北海道"

    def test_no_prefecture(self):
        assert extract_prefecture("西新宿1丁目") is None
