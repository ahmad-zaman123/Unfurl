import ipaddress
import socket
from io import BytesIO
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image

ALLOWED_SCHEMES = ("http", "https")
FETCH_TIMEOUT = 4
MAX_IMAGE_BYTES = 2 * 1024 * 1024


class UnsafeFetchError(Exception):
    pass


class _NoRedirect(HTTPRedirectHandler):
    # Refuse to follow redirects — a redirect could point at a private address
    # after the initial host check passed.
    def redirect_request(self, *args, **kwargs):
        return None


_opener = build_opener(_NoRedirect)


def _assert_public_host(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeFetchError("Host could not be resolved.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        # is_global rejects loopback, private, link-local (169.254.x — cloud
        # metadata), and reserved ranges in one check.
        if not ip.is_global:
            raise UnsafeFetchError("Refusing to fetch a non-public address.")


def fetch_image(url):
    """Fetch a remote image with SSRF protections. Raises UnsafeFetchError."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname:
        raise UnsafeFetchError("Only http(s) URLs are allowed.")

    _assert_public_host(parsed.hostname)

    request = Request(url, headers={"User-Agent": "Unfurl/1.0"})
    try:
        with _opener.open(request, timeout=FETCH_TIMEOUT) as response:
            if not response.headers.get("Content-Type", "").startswith("image/"):
                raise UnsafeFetchError("URL did not return an image.")
            data = response.read(MAX_IMAGE_BYTES + 1)
    except (URLError, OSError) as exc:
        raise UnsafeFetchError("Could not fetch the image.") from exc

    if len(data) > MAX_IMAGE_BYTES:
        raise UnsafeFetchError("Image exceeds the size limit.")

    try:
        image = Image.open(BytesIO(data))
        image.load()
    except OSError as exc:
        raise UnsafeFetchError("Could not decode the image.") from exc

    return image.convert("RGBA")
