# Copyright 2023 Dixmit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import re

import requests

from odoo.tests.common import HttpCase, tagged
from odoo.tools import misc


@tagged("post_install", "-at_install")
class TestSignPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        cls._super_send = requests.Session.send
        super().setUpClass()
        cls.data = base64.b64encode(
            open(
                misc.file_path(f"{cls.test_module}/tests/empty.pdf"),
                "rb",
            ).read()
        )
        cls.signer = cls.env["res.partner"].create({"name": "Signer"})
        cls.request = cls.env["sign.oca.request"].create(
            {
                "data": cls.data,
                "name": "Demo template",
                "signer_ids": [
                    (
                        0,
                        0,
                        {
                            "partner_id": cls.signer.id,
                            "role_id": cls.env.ref("sign_oca.sign_role_customer").id,
                        },
                    )
                ],
            }
        )
        cls.item = cls.request.add_item(
            {
                "role_id": cls.env.ref("sign_oca.sign_role_customer").id,
                "field_id": cls.env.ref("sign_oca.sign_field_name").id,
                "page": 1,
                "position_x": 10,
                "position_y": 10,
                "width": 10,
                "height": 10,
            }
        )

    @classmethod
    def _request_handler(cls, s, r, /, **kw):
        """Don't block external requests."""
        return cls._super_send(s, r, **kw)

    def test_portal(self):
        self.authenticate("portal", "portal")
        self.request.action_send()
        self.url_open(self.request.signer_ids.access_url).raise_for_status()
        self.assertEqual(
            base64.b64decode(self.data),
            self.url_open(
                f"/sign_oca/content/{self.request.signer_ids.id}/{self.request.signer_ids.access_token}"
            ).content,
        )
        self.assertEqual(
            self.url_open(
                f"/sign_oca/info/{self.request.signer_ids.id}/{self.request.signer_ids.access_token}",
                data="{}",
                headers={"Content-Type": "application/json"},
            ).json()["result"]["items"][str(self.item["id"])],
            self.item,
        )
        data = {}
        for key in self.request.signer_ids.get_info()["items"]:
            val = self.request.signer_ids.get_info()["items"][key].copy()
            val["value"] = "My Name"
            data[key] = val

    def test_sign_assets_are_served_without_redirect(self):
        js_response = self.url_open("/sign_oca/get_assets.js", allow_redirects=False)
        self.assertEqual(js_response.status_code, 200)
        self.assertIn("javascript", js_response.headers.get("Content-Type", ""))
        self.assertEqual(js_response.content, b"")
        css_response = self.url_open("/sign_oca/get_assets.css", allow_redirects=False)
        self.assertEqual(css_response.status_code, 200)
        self.assertIn("css", css_response.headers.get("Content-Type", ""))
        self.assertTrue(css_response.content)

    def test_portal_bundle_contains_the_sign_button(self):
        self.request.action_send()
        page = self.url_open(self.request.signer_ids.access_url)
        self.assertEqual(page.status_code, 200)
        bundle_urls = re.findall(
            r"/web/assets/[^\"']+oca_sign\.assets_frontend_sign\.min\.js",
            page.text,
        )
        self.assertTrue(bundle_urls, "The portal bundle must be loaded")
        bundle = self.url_open(bundle_urls[0])
        self.assertEqual(bundle.status_code, 200)
        self.assertIn(b"o_sign_oca_sign_button", bundle.content)
