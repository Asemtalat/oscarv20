from odoo import api, fields, models


class DetailedSaleOrder(models.Model):
    _name = 'detailed.sale.order'
    _description = 'DetailedSaleOrder'

    date_from = fields.Date()
    date_to = fields.Date()
    total_sale_orders_amount = fields.Float(string='Commission')
    credit_note_id = fields.Many2one('account.move')

    s_target_line_id = fields.Many2one('sales.target.line')

    def action_create_credit_note(self):
        name = dict(self.s_target_line_id._fields['name'].selection).get(self.s_target_line_id.name)
        line = [(0, 0, {
            'name': name,
            'quantity': 1,
            'price_unit': self.total_sale_orders_amount,
        })]
        credit_note = self.env['account.move'].create(
            [
                {
                    'partner_id': self.s_target_line_id.contract_id.partner_id.id,
                    'contract_id': self.s_target_line_id.contract_id.id,
                    'move_type': 'out_refund',
                    'ref': 'Credit Note for Contract %s' % self.s_target_line_id.contract_id.name,
                    'line_ids': line
                }
            ]
        )
        self.credit_note_id = credit_note.id
        return credit_note
