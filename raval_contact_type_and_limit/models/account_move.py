from odoo import api, fields, models
from odoo.tools import formatLang


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _credit_limit_partner_check(self, record, current_amount=0.0, exclude_amount=0.0):
        partner_id = record.partner_id.commercial_partner_id
        credit_to_invoice = partner_id.credit_to_invoice - exclude_amount
        total_credit = partner_id.credit + credit_to_invoice + current_amount
        if not partner_id.credit_limit or not partner_id.use_partner_credit_limit or total_credit <= partner_id.credit_limit:
            return 0
        limit = formatLang(self.env, partner_id.credit_limit, currency_obj=record.company_id.currency_id)
        return limit