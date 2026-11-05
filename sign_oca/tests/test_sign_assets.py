# Copyright 2026 Galvintec
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestSignAssets(HttpCase):
    """The assets injected in the pdf.js iframe must not loop.

    ``sign_oca.sign_assets`` only contains stylesheets, but the sign portal
    asks for its JavaScript part too. Serving the empty attachment created by
    ``AssetsBundle.js()`` made the browser redirect to itself until it failed
    with ``net::ERR_TOO_MANY_REDIRECTS``.
    """

    def test_sign_assets_js_is_served_without_redirect(self):
        response = self.url_open("/sign_oca/get_assets.js", allow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers.get("Content-Type", ""))
        self.assertEqual(response.content, b"")

    def test_sign_assets_css_is_still_served(self):
        response = self.url_open("/sign_oca/get_assets.css", allow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn("css", response.headers.get("Content-Type", ""))
        self.assertTrue(response.content)
