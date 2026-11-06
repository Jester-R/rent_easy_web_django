"""Disk-backed image uploads served from ``MEDIA_ROOT`` / ``MEDIA_URL``.

Images are stored as real files instead of base64 data URLs in the database.
The database keeps the public URL (``/media/...``) so serializers and the
Angular client do not need to know how the bytes are stored.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

MAX_IMAGE_BYTES = 15 * 1024 * 1024

# Magic-byte signatures are checked instead of trusting the multipart
# ``Content-Type`` header, which a client can spoof.
_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)


def image_extension(data: bytes) -> str | None:
    """Return the file extension for real image bytes, or ``None``."""
    for signature, extension in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return extension
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def media_base_url() -> str:
    """Return ``MEDIA_URL`` as an absolute site path (``/media/``)."""
    base = settings.MEDIA_URL or "/media/"
    if not base.startswith(("/", "http://", "https://")):
        base = f"/{base}"
    return f"{base.rstrip('/')}/"


def image_url(name: str) -> str:
    return f"{media_base_url()}{name.lstrip('/')}"


def save_image(data: bytes, folder: str) -> str:
    """Persist image bytes under ``MEDIA_ROOT`` and return their public URL.

    Raises ``ValueError`` when the bytes are not a supported image.
    """
    extension = image_extension(data)
    if extension is None:
        raise ValueError("invalid_image_file")
    name = f"{folder.strip('/')}/{uuid.uuid4().hex}.{extension}"
    saved_name = default_storage.save(name, ContentFile(data))
    return image_url(saved_name)


def delete_image_url(url: str) -> None:
    """Delete a previously uploaded file when ``url`` points into media."""
    base = media_base_url()
    if not url or not url.startswith(base):
        return
    name = url[len(base) :]
    if name:
        default_storage.delete(name)
