"""Upload property images to Supabase Storage."""

import hashlib
from pathlib import PurePosixPath

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class ImageUploadService:
    """Downloads images from scraper URLs and uploads them to Supabase Storage."""

    def __init__(
        self,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
        bucket: str | None = None,
    ):
        self.supabase_url = supabase_url or settings.supabase_url
        self.service_role_key = service_role_key or settings.supabase_service_role_key
        self.bucket = bucket or settings.supabase_storage_bucket
        self._client: httpx.AsyncClient | None = None

    @property
    def is_available(self) -> bool:
        return bool(self.supabase_url and self.service_role_key)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def upload_from_url(
        self,
        image_url: str,
        property_id: int,
        index: int = 0,
    ) -> str | None:
        """Download an image from a URL and upload to Supabase Storage.

        Returns the storage path (e.g., "properties/123/0.jpg") or None on failure.
        """
        if not self.is_available:
            logger.debug("Image upload skipped — Supabase Storage not configured")
            return None

        try:
            client = await self._get_client()

            # Download the image
            resp = await client.get(image_url, follow_redirects=True)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "image/jpeg")
            ext = _content_type_to_ext(content_type)

            # Generate storage path
            storage_path = f"properties/{property_id}/{index}{ext}"

            # Upload to Supabase Storage
            upload_url = (
                f"{self.supabase_url}/storage/v1/object/{self.bucket}/{storage_path}"
            )

            upload_resp = await client.post(
                upload_url,
                content=resp.content,
                headers={
                    "Authorization": f"Bearer {self.service_role_key}",
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
            )

            if upload_resp.status_code in (200, 201):
                # Return the full public URL — the Next.js app uses storage_path
                # directly as <img src={storagePath}> with no transformation.
                public_url = (
                    f"{self.supabase_url}/storage/v1/object/public/"
                    f"{self.bucket}/{storage_path}"
                )
                logger.debug(
                    "Image uploaded",
                    property_id=property_id,
                    path=storage_path,
                    url=public_url,
                )
                return public_url
            else:
                logger.warning(
                    "Image upload failed",
                    status=upload_resp.status_code,
                    body=upload_resp.text[:200],
                )
                return None

        except Exception as e:
            logger.warning("Image upload error", url=image_url, error=str(e))
            return None

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


def _content_type_to_ext(content_type: str) -> str:
    """Map content type to file extension."""
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }
    return mapping.get(content_type.split(";")[0].strip().lower(), ".jpg")
