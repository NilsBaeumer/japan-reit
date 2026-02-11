"""Google Translate API integration for translating Japanese text to English."""

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class TranslateService:
    """Translates Japanese text to English using Google Cloud Translation API v2."""

    API_URL = "https://translation.googleapis.com/language/translate/v2"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.google_translate_api_key
        self._client: httpx.AsyncClient | None = None

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def translate(
        self,
        text: str,
        source_lang: str = "ja",
        target_lang: str = "en",
    ) -> str:
        """Translate text from source_lang to target_lang.

        Returns original text if translation fails or API key not configured.
        """
        if not self.api_key:
            logger.debug("Translation skipped — no API key")
            return text

        if not text or not text.strip():
            return text

        # Truncate very long texts (Google API limit is ~5000 chars per request)
        truncated = text[:5000] if len(text) > 5000 else text

        try:
            client = await self._get_client()
            response = await client.post(
                self.API_URL,
                params={"key": self.api_key},
                json={
                    "q": truncated,
                    "source": source_lang,
                    "target": target_lang,
                    "format": "text",
                },
            )
            response.raise_for_status()
            data = response.json()

            translated = data["data"]["translations"][0]["translatedText"]
            logger.debug(
                "Translated text",
                source_len=len(truncated),
                target_len=len(translated),
            )
            return translated

        except Exception as e:
            logger.warning("Translation failed", error=str(e))
            return text

    async def translate_batch(
        self,
        texts: list[str],
        source_lang: str = "ja",
        target_lang: str = "en",
    ) -> list[str]:
        """Translate multiple texts in a single API call (max ~128 items)."""
        if not self.api_key:
            return texts

        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return texts

        try:
            client = await self._get_client()
            response = await client.post(
                self.API_URL,
                params={"key": self.api_key},
                json={
                    "q": valid_texts[:128],
                    "source": source_lang,
                    "target": target_lang,
                    "format": "text",
                },
            )
            response.raise_for_status()
            data = response.json()

            translations = [
                t["translatedText"]
                for t in data["data"]["translations"]
            ]

            # Map back to original list (preserving empty/None entries)
            result = []
            trans_idx = 0
            for t in texts:
                if t and t.strip() and trans_idx < len(translations):
                    result.append(translations[trans_idx])
                    trans_idx += 1
                else:
                    result.append(t)
            return result

        except Exception as e:
            logger.warning("Batch translation failed", error=str(e))
            return texts

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
