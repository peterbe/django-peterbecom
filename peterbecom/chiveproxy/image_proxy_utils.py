import hashlib
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone

NO_CONVERT_FILE_EXTENSIONS = ("mp4", "avif")


def url_to_destination(url: str) -> tuple[str, Path, Path]:
    cache_root = settings.IMAGE_PROXY_CACHE_ROOT
    if not cache_root.exists():
        cache_root.mkdir(parents=True)

    seed = f"{settings.SECRET_KEY}:{url}"
    seeded = _seeded_token(seed)
    file_extension = urlparse(url).path.split(".")[-1]
    prefix = ""
    if settings.RUNNING_TESTS:
        prefix = "test-"
    origin_destination_file_name = cache_root / f"{prefix}{seeded}.{file_extension}"

    destination_file_extension = (
        file_extension if file_extension in NO_CONVERT_FILE_EXTENSIONS else "webp"
    )
    destination_file_name = (
        cache_root
        / seeded[:4]
        / seeded[4:6]
        / seeded[6:8]
        / seeded[8:9]
        / f"{prefix}{seeded[9:]}.{destination_file_extension}"
    )

    return (
        destination_file_extension,
        origin_destination_file_name,
        destination_file_name,
    )


def _seeded_token(seed: str, length=16) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    date_prefix = timezone.now().strftime("%Y%m%d")
    return f"{date_prefix}{digest}"[:length]
