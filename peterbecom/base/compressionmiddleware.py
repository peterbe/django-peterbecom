"""
Brotli + Zstandard compression middleware for selected URL prefixes.

Install:
    pip install brotli               # for "br"
    pip install zstandard            # for "zstd" (not needed on Python 3.14+,
                                     # which ships compression.zstd)

settings.py:
    MIDDLEWARE = [
        "yourapp.api_compression.CompressionMiddleware",
        # ... everything else
    ]

    # Optional overrides (defaults shown)
    COMPRESSION_PATH_PREFIXES = ("/chiveproxy/api",)
    COMPRESSION_MIN_SIZE = 1024             # bytes; smaller bodies sent as-is
    COMPRESSION_PREFERENCE = ("zstd", "br") # tie-breaker when client q-values are equal
    BROTLI_QUALITY = 5                      # 0-11
    ZSTD_LEVEL = 3                          # 1-19; keep moderate for dynamic responses
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.cache import patch_vary_headers

try:
    import brotli
except ImportError:
    brotli = None

try:
    from compression import zstd as std_zstd  # Python 3.14+
except ImportError:
    std_zstd = None

try:
    import zstandard
except ImportError:
    zstandard = None

print((std_zstd, zstandard))
COMPRESSIBLE_TYPES = {"application/json"}


def _build_codecs(br_quality, zstd_level):
    """Map encoding token -> compress(bytes) -> bytes, for installed libraries only."""
    codecs = {}
    if brotli is not None:
        codecs["br"] = lambda data: brotli.compress(
            data, quality=br_quality, mode=brotli.MODE_TEXT
        )
    if std_zstd is not None:
        codecs["zstd"] = lambda data: std_zstd.compress(data, level=zstd_level)
    elif zstandard is not None:
        # ZstdCompressor instances aren't safe to share across threads,
        # so create one per call (cheap relative to the compression itself).
        codecs["zstd"] = lambda data: zstandard.ZstdCompressor(
            level=zstd_level
        ).compress(data)
    return codecs


def _parse_accept_encoding(header: str) -> dict:
    """Parse Accept-Encoding into {token: q}."""
    prefs = {}
    for part in header.split(","):
        token, _, params = part.strip().partition(";")
        token = token.strip().lower()
        if not token:
            continue
        q = 1.0
        for param in params.split(";"):
            key, _, value = param.strip().partition("=")
            if key.strip().lower() == "q":
                try:
                    q = float(value)
                except ValueError:
                    q = 0.0
        prefs[token] = q
    return prefs


def _choose_encoding(header: str, available: tuple):
    """
    Pick the encoding with the highest client q-value.
    `available` is ordered by server preference, which breaks ties.
    Returns None if the client accepts none of them.
    """
    prefs = _parse_accept_encoding(header)
    wildcard_q = prefs.get("*", 0.0)
    best, best_q = None, 0.0
    for encoding in available:
        q = prefs.get(encoding, wildcard_q)
        if q > best_q:
            best, best_q = encoding, q
    return best


def _is_compressible_type(content_type: str) -> bool:
    mime = content_type.split(";")[0].strip().lower()
    return mime in COMPRESSIBLE_TYPES or mime.endswith("+json")


class CompressionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.prefixes = tuple(
            getattr(settings, "COMPRESSION_PATH_PREFIXES", ("/chiveproxy/api",))
        )
        self.min_size = getattr(settings, "COMPRESSION_MIN_SIZE", 1024)

        self.codecs = _build_codecs(
            br_quality=getattr(settings, "BROTLI_QUALITY", 5),
            zstd_level=getattr(settings, "ZSTD_LEVEL", 3),
        )
        preference = getattr(settings, "COMPRESSION_PREFERENCE", ("zstd", "br"))
        self.available = tuple(enc for enc in preference if enc in self.codecs)
        if not self.available:
            raise ImproperlyConfigured(
                "CompressionMiddleware: install 'brotli' and/or 'zstandard'."
            )

    def __call__(self, request):
        response = self.get_response(request)

        if not request.path.startswith(self.prefixes):
            return response

        if response.streaming or response.has_header("Content-Encoding"):
            return response

        if not _is_compressible_type(response.get("Content-Type", "")):
            return response

        if len(response.content) < self.min_size:
            return response

        # The representation now depends on Accept-Encoding, even for
        # clients that end up with the uncompressed version.
        patch_vary_headers(response, ("Accept-Encoding",))

        encoding = _choose_encoding(
            request.META.get("HTTP_ACCEPT_ENCODING", ""), self.available
        )
        if encoding is None:
            return response

        compressed = self.codecs[encoding](response.content)
        if len(compressed) >= len(response.content):
            return response

        response.content = compressed
        response["Content-Length"] = str(len(compressed))
        response["Content-Encoding"] = encoding

        etag = response.get("ETag")
        if etag and etag.startswith('"'):
            response["ETag"] = "W/" + etag

        return response
