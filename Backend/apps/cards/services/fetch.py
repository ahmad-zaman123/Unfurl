import http.client
import ipaddress
import socket
import ssl
import time
from io import BytesIO
from urllib.parse import urlparse

from PIL import Image

ALLOWED_SCHEMES = ("http", "https")
FETCH_TIMEOUT = 4
MAX_IMAGE_BYTES = 2 * 1024 * 1024
# A logo never needs more. Checked before decoding, so a small file that unpacks to a huge picture is refused.
MAX_IMAGE_PIXELS = 4096 * 4096
IMAGE_FORMATS = ("PNG", "JPEG", "GIF", "WEBP")

# IPv6 ranges that carry an IPv4 address inside them (NAT64), checked against the IPv4 rules too.
_NAT64 = (ipaddress.ip_network("64:ff9b::/96"), ipaddress.ip_network("64:ff9b:1::/48"))


class UnsafeFetchError(Exception):
    pass


def _is_public(ip):
    if not ip.is_global:
        return False
    if ip.version == 6:
        embedded = ip.ipv4_mapped or ip.sixtofour or (ip.teredo[1] if ip.teredo else None)
        if embedded is None and any(ip in net for net in _NAT64):
            embedded = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if embedded is not None and not embedded.is_global:
            return False
    return True


def _public_address(host):
    """Resolve the host once and return an address to connect to. Every address it has must be public."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeFetchError("Host could not be resolved.") from exc
    addresses = [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]
    # is_global rejects loopback, private, link-local (169.254.x, cloud metadata) and reserved ranges.
    if not addresses or not all(_is_public(ip) for ip in addresses):
        raise UnsafeFetchError("Refusing to fetch a non-public address.")
    return str(addresses[0])


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """Connects to an address that was already checked, so a second DNS answer can't swap in a private one."""

    def __init__(self, host, address, **kwargs):
        super().__init__(host, **kwargs)
        self._address = address

    def connect(self):
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, **kwargs):
        super().__init__(host, context=ssl.create_default_context(), **kwargs)
        self._address = address

    def connect(self):
        sock = socket.create_connection((self._address, self.port), self.timeout)
        # The certificate is still checked against the real host name.
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _get(parsed, address):
    """GET the URL from the checked address. Returns (content type, body). Redirects are not followed."""
    secure = parsed.scheme == "https"
    connection_class = _PinnedHTTPSConnection if secure else _PinnedHTTPConnection
    connection = connection_class(parsed.hostname, address, port=parsed.port, timeout=FETCH_TIMEOUT)
    path = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
    deadline = time.monotonic() + FETCH_TIMEOUT * 2
    try:
        connection.request("GET", path, headers={"User-Agent": "Unfurl/1.0", "Accept": "image/*"})
        response = connection.getresponse()
        # A redirect could point at a private address after the check passed, so it counts as a failure.
        if response.status != 200:
            raise UnsafeFetchError("Could not fetch the image.")
        content_type = response.getheader("Content-Type", "")
        if not content_type.startswith("image/"):
            raise UnsafeFetchError("URL did not return an image.")
        chunks, size = [], 0
        while size <= MAX_IMAGE_BYTES:
            # A server that trickles bytes can't hold the request open past the deadline.
            if time.monotonic() > deadline:
                raise UnsafeFetchError("The image took too long to download.")
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        return content_type, b"".join(chunks)
    except (OSError, http.client.HTTPException) as exc:
        raise UnsafeFetchError("Could not fetch the image.") from exc
    finally:
        connection.close()


def _decode(data):
    try:
        image = Image.open(BytesIO(data), formats=IMAGE_FORMATS)
        width, height = image.size
        if width * height > MAX_IMAGE_PIXELS:
            raise UnsafeFetchError("Image is too large.")
        image.load()
    except UnsafeFetchError:
        raise
    except Exception as exc:  # Pillow raises many kinds of errors for broken or hostile files.
        raise UnsafeFetchError("Could not decode the image.") from exc
    return image.convert("RGBA")


def fetch_image(url):
    """Fetch a remote image with SSRF protections. Raises UnsafeFetchError."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname:
        raise UnsafeFetchError("Only http(s) URLs are allowed.")
    try:
        parsed.port
    except ValueError as exc:
        raise UnsafeFetchError("Invalid port.") from exc

    address = _public_address(parsed.hostname)
    _, data = _get(parsed, address)
    if len(data) > MAX_IMAGE_BYTES:
        raise UnsafeFetchError("Image exceeds the size limit.")
    return _decode(data)
