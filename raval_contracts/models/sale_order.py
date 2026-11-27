from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit ='sale.order'

    contract_id = fields.Many2one('rav.contracts', string='Contract')

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    contract_disc = fields.Float(string='Contract Discount', compute='_get_fixed_contract_disc', store=1)

    @api.depends('order_id.contract_id.fixed_discount')
    def _get_fixed_contract_disc(self):
        for line in self:
            line.contract_disc = 0.0
            if line.order_id.contract_id:
                line.contract_disc = line.order_id.contract_id.fixed_discount

    # @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'contract_disc')
    # def _compute_amount(self):
    #     for line in self:
    #         res = super(SaleOrderLine, line)._compute_amount()
    #         line.price_subtotal = line.price_subtotal - (line.price_subtotal * line.contract_disc)
    #         return res