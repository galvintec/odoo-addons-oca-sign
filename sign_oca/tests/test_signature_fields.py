# Copyright 2026 Galvintec
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from base64 import b64encode

from odoo import Command
from odoo.exceptions import UserError
from odoo.modules.module import get_module_resource
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSignatureFields(TransactionCase):
    """Requests without fields get a required signature field per role."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(get_module_resource("sign_oca", "tests", "empty.pdf"), "rb") as pdf:
            cls.pdf = b64encode(pdf.read())
        cls.role_customer = cls.env.ref("sign_oca.sign_role_customer")
        cls.role_employee = cls.env.ref("sign_oca.sign_role_employee")
        cls.partner = cls.env["res.partner"].create(
            {"name": "Signer", "email": "signer@example.com"}
        )

    def _create_request(self, roles=None, state="1_draft"):
        roles = roles or self.role_customer
        return (
            self.env["sign.oca.request"]
            .sudo()
            .create(
                {
                    "name": "Signature fields request",
                    "data": self.pdf,
                    "state": state,
                    "signer_ids": [
                        Command.create(
                            {
                                "partner_id": self.partner.id,
                                "role_id": role.id,
                            }
                        )
                        for role in roles
                    ],
                }
            )
        )

    def test_send_places_a_required_signature_field(self):
        request = self._create_request()
        self.assertFalse(request.signatory_data)
        request.action_send()
        self.assertEqual(request.state, "0_sent")
        self.assertEqual(len(request.signatory_data), 1)
        item = next(iter(request.signatory_data.values()))
        self.assertEqual(item["field_type"], "signature")
        self.assertTrue(item["required"])
        self.assertEqual(item["role_id"], self.role_customer.id)
        self.assertEqual(item["page"], 1)
        self.assertFalse(item["value"])

    def test_one_field_per_distinct_role(self):
        request = self._create_request(roles=self.role_customer | self.role_employee)
        request.action_send()
        items = list(request.signatory_data.values())
        self.assertEqual(len(items), 2)
        self.assertEqual(
            {item["role_id"] for item in items},
            {self.role_customer.id, self.role_employee.id},
        )
        # Fields must not overlap
        self.assertEqual(len({item["position_y"] for item in items}), 2)

    def test_same_role_is_not_duplicated(self):
        colleague = self.env["res.partner"].create({"name": "Colleague"})
        request = (
            self.env["sign.oca.request"]
            .sudo()
            .create(
                {
                    "name": "Same role request",
                    "data": self.pdf,
                    "signer_ids": [
                        Command.create(
                            {
                                "partner_id": partner.id,
                                "role_id": self.role_customer.id,
                            }
                        )
                        for partner in (self.partner, colleague)
                    ],
                }
            )
        )
        request.action_send()
        self.assertEqual(len(request.signatory_data), 1)

    def test_action_auto_place_signature_fields(self):
        request = self._create_request(state="0_sent")
        request.action_auto_place_signature_fields()
        self.assertEqual(len(request.signatory_data), 1)

    def test_action_auto_place_refuses_requests_with_fields(self):
        request = self._create_request()
        request.action_auto_place_signature_fields()
        with self.assertRaises(UserError):
            request.action_auto_place_signature_fields()

    def test_action_auto_place_requires_signers(self):
        request = (
            self.env["sign.oca.request"]
            .sudo()
            .create({"name": "No signers", "data": self.pdf})
        )
        with self.assertRaises(UserError):
            request.action_auto_place_signature_fields()

    def test_action_auto_place_refuses_signed_requests(self):
        request = self._create_request(state="2_signed")
        with self.assertRaises(UserError):
            request.action_auto_place_signature_fields()
