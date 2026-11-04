# Copyright 2026 Galvintec
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class SignOcaRequestSigner(models.Model):
    """Add the signing order to the request signers."""

    _inherit = "sign.oca.request.signer"
    _order = "sequence, id"

    sequence = fields.Integer(
        string="Signing Order",
        default=10,
        help="Signing order. Lower numbers sign first.",
    )
    is_current = fields.Boolean(
        help="Checked when this signer is the one allowed to sign now.",
    )

    @api.depends(
        "signed_on",
        "partner_id",
        "is_current",
        "request_id.signing_order_enforced",
    )
    @api.depends_context("uid")
    def _compute_is_allow_signature(self):
        result = super()._compute_is_allow_signature()
        for signer in self:
            if (
                signer.request_id.signing_order_enforced
                and not signer.is_current
                and not signer.signed_on
            ):
                signer.is_allow_signature = False
        return result

    def action_sign(self, items, access_token=False, latitude=False, longitude=False):
        result = super().action_sign(
            items,
            access_token=access_token,
            latitude=latitude,
            longitude=longitude,
        )
        self.request_id._post_sign_notify_next()
        return result
