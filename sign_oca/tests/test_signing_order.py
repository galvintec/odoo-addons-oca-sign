# Copyright 2026 Galvintec
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from base64 import b64encode

from odoo import Command, fields
from odoo.modules.module import get_module_resource
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSigningOrder(TransactionCase):
    """Signers are notified one by one following the signing order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(get_module_resource("sign_oca", "tests", "empty.pdf"), "rb") as pdf:
            cls.pdf = b64encode(pdf.read())
        cls.role = cls.env.ref("sign_oca.sign_role_customer")
        cls.partner_1 = cls.env["res.partner"].create(
            {"name": "Signer One", "email": "signer1@example.com"}
        )
        cls.partner_2 = cls.env["res.partner"].create(
            {"name": "Signer Two", "email": "signer2@example.com"}
        )

    def _create_request(self, enforce_order=True):
        return (
            self.env["sign.oca.request"]
            .sudo()
            .create(
                {
                    "name": "Signing order request",
                    "data": self.pdf,
                    "signing_order_enforced": enforce_order,
                    "signer_ids": [
                        Command.create(
                            {
                                "partner_id": partner.id,
                                "role_id": self.role.id,
                                "sequence": sequence,
                            }
                        )
                        for partner, sequence in (
                            (self.partner_1, 1),
                            (self.partner_2, 2),
                        )
                    ],
                }
            )
        )

    def test_signers_are_sorted_by_sequence(self):
        request = self._create_request()
        self.assertEqual(
            request.signer_ids.mapped("partner_id"),
            self.partner_1 | self.partner_2,
        )

    def test_next_pending_signer(self):
        request = self._create_request()
        self.assertEqual(request._get_next_pending_signer().partner_id, self.partner_1)
        first = request.signer_ids[0]
        first.signed_on = fields.Datetime.now()
        self.assertEqual(request._get_next_pending_signer().partner_id, self.partner_2)

    def test_signing_order_advances(self):
        request = self._create_request()
        first, second = request.signer_ids
        request.action_send()
        self.assertEqual(request.state, "0_sent")
        self.assertTrue(first.is_current)
        self.assertFalse(second.is_current)

        first.signed_on = fields.Datetime.now()
        request._post_sign_notify_next()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)

        second.signed_on = fields.Datetime.now()
        request._post_sign_notify_next()
        self.assertFalse(first.is_current)
        self.assertFalse(second.is_current)

    def test_signing_blocked_out_of_turn(self):
        request = self._create_request()
        request.action_send()
        _, second = request.signer_ids
        second_user = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Signer Two User",
                    "login": "signer_two_user",
                    "email": self.partner_2.email,
                    "partner_id": self.partner_2.id,
                    "groups_id": [Command.set([self.env.ref("base.group_user").id])],
                }
            )
        )
        self.assertFalse(second.with_user(second_user).sudo().is_allow_signature)
        request.signer_ids[0].signed_on = fields.Datetime.now()
        request._post_sign_notify_next()
        self.assertTrue(second.with_user(second_user).sudo().is_allow_signature)

    def test_signing_order_not_enforced(self):
        request = self._create_request(enforce_order=False)
        request.action_send()
        self.assertFalse(request.signer_ids.filtered("is_current"))
