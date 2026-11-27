from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.constrains('partner_id', 'amount_total')
    def _check_partner_credit_limit(self):
        """
        Check if the partner's credit limit is exceeded when creating or modifying a sale order.
        """
        for order in self:
            exceed_credit_limit = self.env['account.move']._credit_limit_partner_check(
                order,
                current_amount=(order.amount_total / order.currency_rate),
            )
            partner_name = order.partner_id.name
            credit_limit = exceed_credit_limit
            if exceed_credit_limit:
                raise ValidationError(f'{partner_name} has reached his credit limit of: {credit_limit}')
