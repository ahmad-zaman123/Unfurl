import socket
from io import BytesIO
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.apikeys.models import ApiKey
from apps.cards.services import fetch
from apps.cards.services.cache import cache_stats
from apps.cards.services.fetch import MAX_IMAGE_BYTES, UnsafeFetchError, fetch_image
from apps.cards.services.renderer import render_card
from apps.cards.services.signing import sign, verify
from apps.users.models import User

CARDS = "/api/v1/cards"
OG = "/api/v1/og"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def resolves_to(*ips):
    """Patch DNS so a host resolves to the given addresses, without touching the network."""
    return patch.object(
        fetch.socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in ips]
    )


def image_bytes(size=(4, 4), format="PNG"):
    buffer = BytesIO()
    Image.new("RGB", size, (255, 0, 0)).save(buffer, format=format)
    return buffer.getvalue()


def serves(body, content_type="image/png"):
    """Pretend the remote server answered with this body, without touching the network."""
    return patch.object(fetch, "_get", return_value=(content_type, body))


class LocalServer:
    """A real HTTP server on 127.0.0.1 for testing the connection itself. Each test sets how it answers."""

    def __init__(self, answer):
        seen = self.seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.headers.get("Host"))
                answer(self)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]

    def __enter__(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


class CardTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(email="sara@example.com", password="first-password-1")
        _, raw = ApiKey.generate(owner=self.user, name="Production")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {raw}"}

    def create(self, **spec):
        return self.client.post(CARDS, {"title": "Hello", **spec}, format="json", **self.auth)

    def signed_query(self, **spec):
        response = self.create(**spec)
        self.assertEqual(response.status_code, 200, response.content)
        return dict(parse_qsl(urlsplit(response.json()["url"]).query))

    def og(self, params):
        return self.client.get(OG + "?" + urlencode(params))


class CardTests(CardTestCase):
    def test_creating_a_card_returns_a_signed_url_that_renders(self):
        url = self.create(subtitle="World", theme="dark").json()["url"]
        parts = urlsplit(url)
        self.assertEqual(parts.path, OG)
        params = dict(parse_qsl(parts.query))
        self.assertEqual(params["title"], "Hello")
        self.assertEqual(params["theme"], "dark")
        self.assertNotIn("logo", params)  # blank fields are left out

        response = self.client.get(parts.path + "?" + parts.query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Cache-Control"], "public, max-age=86400")
        self.assertTrue(response.content.startswith(PNG_MAGIC))
        self.assertEqual(Image.open(BytesIO(response.content)).size, (1200, 630))

    @override_settings(UNFURL_PUBLIC_BASE_URL="https://cards.example.com/")
    def test_urls_use_the_public_base_when_set(self):
        url = self.create().json()["url"]
        self.assertTrue(url.startswith("https://cards.example.com/api/v1/og?"))

    def test_the_same_card_is_rendered_once_then_cached(self):
        params = self.signed_query()
        with patch("apps.cards.views.render_card", wraps=render_card) as renderer:
            first = self.og(params)
            second = self.og(params)
        self.assertEqual((first["X-Cache"], second["X-Cache"]), ("MISS", "HIT"))
        self.assertEqual(first.content, second.content)
        renderer.assert_called_once()
        self.assertEqual(cache_stats(), {"hits": 1, "misses": 1, "served": 2, "hit_rate": 50.0})

    def test_cards_still_render_when_the_cache_is_down(self):
        params = self.signed_query()
        with patch("apps.cards.services.cache.cache") as broken, self.assertLogs("apps.cards.services.cache", "WARNING"):
            broken.get.side_effect = ConnectionError("redis down")
            broken.set.side_effect = ConnectionError("redis down")
            broken.add.side_effect = ConnectionError("redis down")
            response = self.og(params)
            stats = cache_stats()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(stats["served"], 0)

    def test_every_template_and_theme_renders(self):
        for template in ("generic", "article", "product", "event"):
            for theme in ("brand", "light", "dark"):
                png = render_card(template=template, theme=theme, title="T", price="$9", date="Today", location="Here")
                self.assertTrue(png.startswith(PNG_MAGIC), (template, theme))

    def test_bad_specs_are_rejected(self):
        cases = [
            ({"accent": "red"}, "accent"),
            ({"accent": "#12345"}, "accent"),
            ({"template": "poster"}, "template"),
            ({"theme": "neon"}, "theme"),
            ({"title": ""}, "title"),
            ({"title": "x" * 201}, "title"),
            ({"footer": "x" * 121}, "footer"),
            ({"logo": "ftp://example.com/logo.png"}, "logo"),
            ({"logo": "not a url"}, "logo"),
        ]
        for spec, field in cases:
            response = self.create(**spec)
            self.assertEqual(response.status_code, 400, spec)
            self.assertIn(field, response.json(), spec)

    def test_short_hex_accent_is_accepted(self):
        self.assertEqual(self.create(accent="#0af").status_code, 200)

    def test_control_characters_are_stripped(self):
        params = self.signed_query(title="Hel\x1blo\x07", subtitle="line one\nline two")
        self.assertEqual(params["title"], "Hello")
        self.assertEqual(params["subtitle"], "line one\nline two")

    def test_null_characters_are_rejected(self):
        self.assertEqual(self.create(title="Hel\x00lo").status_code, 400)


class SigningTests(CardTestCase):
    def test_changing_any_value_breaks_the_signature(self):
        params = self.signed_query(subtitle="World")
        for field, value in (("title", "Hacked"), ("subtitle", "Other"), ("theme", "light")):
            response = self.og({**params, field: value})
            self.assertEqual(response.status_code, 403, field)
            self.assertEqual(response.json()["detail"], "Invalid or missing signature.")

    def test_adding_or_removing_a_value_breaks_the_signature(self):
        params = self.signed_query(subtitle="World")
        self.assertEqual(self.og({**params, "logo": "https://example.com/x.png"}).status_code, 403)
        without = {k: v for k, v in params.items() if k != "subtitle"}
        self.assertEqual(self.og(without).status_code, 403)

    def test_missing_or_forged_signature_is_refused(self):
        params = self.signed_query()
        unsigned = {k: v for k, v in params.items() if k != "sig"}
        self.assertEqual(self.og(unsigned).status_code, 403)
        self.assertEqual(self.og({**unsigned, "sig": "0" * 64}).status_code, 403)
        self.assertEqual(self.og({**unsigned, "sig": ""}).status_code, 403)

    def test_a_refused_request_renders_nothing(self):
        params = self.signed_query()
        with patch("apps.cards.views.render_card") as renderer:
            self.og({**params, "title": "Hacked"})
        renderer.assert_not_called()

    def test_signature_ignores_parameter_order(self):
        self.assertEqual(sign({"a": "1", "b": "2"}), sign({"b": "2", "a": "1"}))
        self.assertTrue(verify({"a": "1"}, sign({"a": "1"})))
        self.assertFalse(verify({"a": "1"}, None))

    def test_changing_the_secret_invalidates_old_urls(self):
        params = self.signed_query()
        with override_settings(CARD_SIGNING_SECRET="a-different-secret-0123456789"):
            self.assertEqual(self.og(params).status_code, 403)
        self.assertEqual(self.og(params).status_code, 200)

    def test_rendering_needs_no_sign_in(self):
        params = self.signed_query()
        self.assertEqual(APIClient().get(OG + "?" + urlencode(params)).status_code, 200)


class SafeFetchTests(SimpleTestCase):
    """The logo fetcher must never reach private networks or cloud metadata."""

    def test_only_http_and_https_are_allowed(self):
        for url in ("file:///etc/passwd", "ftp://example.com/x.png", "gopher://example.com/", "http:///nohost",
                    "https://example.com:99999/x.png"):
            with self.assertRaises(UnsafeFetchError, msg=url):
                fetch_image(url)

    def test_private_and_special_addresses_are_refused(self):
        blocked = [
            "127.0.0.1",
            "10.0.0.5",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",  # cloud metadata
            "0.0.0.0",
            "100.64.0.1",  # carrier-grade NAT
            "::1",
            "fc00::1",
            "fe80::1",
            "::ffff:127.0.0.1",  # IPv4 written as IPv6
            "::ffff:169.254.169.254",
            "64:ff9b::a9fe:a9fe",  # NAT64 form of 169.254.169.254
            "2002:7f00:1::1",  # 6to4 form of 127.0.0.1
        ]
        for ip in blocked:
            with resolves_to(ip), patch.object(fetch, "_get") as get:
                with self.assertRaises(UnsafeFetchError, msg=ip):
                    fetch_image("https://logo.example.com/x.png")
                get.assert_not_called()

    def test_a_host_with_any_private_address_is_refused(self):
        with resolves_to("93.184.216.34", "10.0.0.5"), patch.object(fetch, "_get") as get:
            with self.assertRaises(UnsafeFetchError):
                fetch_image("https://logo.example.com/x.png")
        get.assert_not_called()

    def test_unresolvable_hosts_are_refused(self):
        with patch.object(fetch.socket, "getaddrinfo", side_effect=socket.gaierror("nope")):
            with self.assertRaises(UnsafeFetchError):
                fetch_image("https://no-such-host.example/x.png")

    def test_the_host_is_resolved_once_and_the_checked_address_is_used(self):
        # DNS rebinding: a second lookup could answer with a private address. There is no second lookup.
        with resolves_to("93.184.216.34") as lookup, serves(image_bytes()) as get:
            fetch_image("https://logo.example.com/x.png")
        self.assertEqual(lookup.call_count, 1)
        self.assertEqual(get.call_args.args[1], "93.184.216.34")

    def test_the_connection_goes_to_the_checked_address_and_names_the_real_host(self):
        def answer(handler):
            body = image_bytes()
            handler.send_response(200)
            handler.send_header("Content-Type", "image/png")
            handler.send_header("Content-Length", str(len(body)))
            handler.end_headers()
            handler.wfile.write(body)

        real_lookup = socket.getaddrinfo
        with LocalServer(answer) as server, patch.object(fetch.socket, "getaddrinfo", side_effect=real_lookup) as lookup:
            content_type, body = fetch._get(urlparse(f"http://logo.example.com:{server.port}/x.png"), "127.0.0.1")
        # The host name is never looked up again. Only the checked address is used.
        self.assertNotIn("logo.example.com", [call.args[0] for call in lookup.call_args_list])
        self.assertEqual((content_type, body[:8]), ("image/png", PNG_MAGIC))
        self.assertEqual(server.seen, [f"logo.example.com:{server.port}"])

    def test_redirects_are_not_followed(self):
        def answer(handler):
            handler.send_response(302)
            handler.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            handler.end_headers()

        with LocalServer(answer) as server:
            with self.assertRaises(UnsafeFetchError):
                fetch._get(urlparse(f"http://logo.example.com:{server.port}/x.png"), "127.0.0.1")
        self.assertEqual(len(server.seen), 1)

    def test_a_server_that_trickles_bytes_is_cut_off(self):
        def answer(handler):
            handler.send_response(200)
            handler.send_header("Content-Type", "image/png")
            handler.end_headers()
            try:
                for _ in range(50):
                    handler.wfile.write(b"x" * 64 * 1024)
                    handler.wfile.flush()
                    time.sleep(0.1)
            except OSError:
                pass  # the fetcher hung up, as it should

        with LocalServer(answer) as server, patch.object(fetch, "FETCH_TIMEOUT", 0.25):
            started = time.monotonic()
            with self.assertRaises(UnsafeFetchError):
                fetch._get(urlparse(f"http://logo.example.com:{server.port}/x.png"), "127.0.0.1")
        self.assertLess(time.monotonic() - started, 2)

    def test_a_public_image_is_fetched(self):
        with resolves_to("93.184.216.34"), serves(image_bytes()):
            image = fetch_image("https://logo.example.com/x.png")
        self.assertEqual((image.mode, image.size), ("RGBA", (4, 4)))

    def test_non_images_are_refused(self):
        def answer(handler):
            handler.send_response(200)
            handler.send_header("Content-Type", "text/html")
            handler.end_headers()
            handler.wfile.write(b"<html></html>")

        with LocalServer(answer) as server:
            with self.assertRaises(UnsafeFetchError):
                fetch._get(urlparse(f"http://logo.example.com:{server.port}/x.png"), "127.0.0.1")

    def test_oversized_files_are_refused(self):
        with resolves_to("93.184.216.34"), serves(b"\0" * (MAX_IMAGE_BYTES + 10)):
            with self.assertRaises(UnsafeFetchError):
                fetch_image("https://logo.example.com/x.png")

    def test_a_small_file_that_unpacks_to_a_huge_picture_is_refused_before_decoding(self):
        bomb = image_bytes((5000, 5000))
        self.assertLess(len(bomb), MAX_IMAGE_BYTES)
        with resolves_to("93.184.216.34"), serves(bomb), patch.object(Image.Image, "load") as load:
            with self.assertRaisesMessage(UnsafeFetchError, "too large"):
                fetch_image("https://logo.example.com/x.png")
        load.assert_not_called()

    def test_only_common_web_image_formats_are_decoded(self):
        for format in ("PNG", "JPEG", "GIF", "WEBP"):
            with resolves_to("93.184.216.34"), serves(image_bytes(format=format)):
                self.assertEqual(fetch_image("https://logo.example.com/x.png").size, (4, 4), format)
        for format in ("BMP", "TIFF", "ICO"):
            with resolves_to("93.184.216.34"), serves(image_bytes(format=format)):
                with self.assertRaises(UnsafeFetchError, msg=format):
                    fetch_image("https://logo.example.com/x.png")

    def test_broken_images_and_network_errors_are_refused(self):
        with resolves_to("93.184.216.34"):
            with serves(b"not really a png"):
                with self.assertRaises(UnsafeFetchError):
                    fetch_image("https://logo.example.com/x.png")
        # Nothing listens on this port, so the connection itself fails.
        with LocalServer(lambda handler: None) as server:
            port = server.port
        with self.assertRaises(UnsafeFetchError):
            fetch._get(urlparse(f"http://logo.example.com:{port}/x.png"), "127.0.0.1")

    def test_a_blocked_logo_still_renders_the_card(self):
        with resolves_to("169.254.169.254"), patch.object(fetch, "_get") as get:
            png = render_card(title="Hello", logo="https://logo.example.com/x.png")
        self.assertTrue(png.startswith(PNG_MAGIC))
        get.assert_not_called()

    def test_a_good_logo_is_drawn_on_the_card(self):
        with resolves_to("93.184.216.34"), serves(image_bytes((200, 200))):
            with_logo = render_card(title="Hello", theme="light", logo="https://logo.example.com/x.png")
        without = render_card(title="Hello", theme="light")
        self.assertNotEqual(with_logo, without)
